"""Transaction categorization using Claude and manual overrides."""

from typing import List

from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from tenacity import retry, stop_after_attempt, wait_exponential

from sprig.database import SprigDatabase
from sprig.logger import get_logger
from sprig.models import TransactionCategory, TransactionView, TransactionBatch
from sprig.models.config import Config

logger = get_logger("sprig.categorize")



def _validate_category_results(
    categories: List[TransactionCategory],
    valid_category_names: set[str]
) -> List[TransactionCategory]:
    """Filter out invalid categories from AI results.

    Args:
        categories: List of categories returned from AI
        valid_category_names: Set of valid category names from config

    Returns:
        List containing only categories with valid names
    """
    validated = []
    for category in categories:
        if category.category in valid_category_names:
            validated.append(category)
        else:
            logger.warning(
                f"Invalid category '{category.category}' for "
                f"{category.transaction_id}, skipping"
            )
    return validated


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    reraise=True,
)
def categorize_inferentially(
    transaction_views: List[TransactionView],
    config: Config,
) -> List[TransactionCategory]:
    if not transaction_views:
        return []

    categories_with_descriptions = [
        f"{cat.name}: {cat.description}" for cat in config.categories
    ]

    batch = TransactionBatch(transactions=transaction_views)
    transactions_json = batch.model_dump_json(indent=2)

    prompt = config.categorization_prompt.format(
        categories=", ".join(categories_with_descriptions),
        transactions=transactions_json
    )

    provider = AnthropicProvider(api_key=config.claude_key)
    model = AnthropicModel("claude-haiku-4-5-20251001", provider=provider)

    agent = Agent(
        model,
        output_type=list[TransactionCategory],
        retries=3,
    )

    try:
        result = agent.run_sync(prompt)
        categories = result.output
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to categorize {len(transaction_views)} transactions: {error_msg}")

        # Re-raise rate limit errors so sync can handle them specially
        if "rate" in error_msg.lower() and "limit" in error_msg.lower():
            raise

        return []

    valid_category_names = {cat.name for cat in config.categories}
    return _validate_category_results(categories, valid_category_names)


def categorize_in_batches(
    transaction_views: List[TransactionView],
    config: Config,
) -> List[TransactionCategory]:
    if not transaction_views:
        return []

    batch_size = config.batch_size
    total_transactions = len(transaction_views)
    total_batches = (total_transactions + batch_size - 1) // batch_size
    all_results = []

    logger.info(f"Categorizing {total_transactions} transaction(s) using Claude AI")
    logger.info(f"   Processing in {total_batches} batch(es) of up to {batch_size} each")

    if total_transactions > 100:
        logger.info("   Large transaction volume may hit Claude API rate limits")

    for i in range(0, len(transaction_views), batch_size):
        batch = transaction_views[i : i + batch_size]
        batch_num = (i // batch_size) + 1

        results = categorize_inferentially(batch, config)
        all_results.extend(results)

        success_count = len(results)
        batch_size_actual = len(batch)

        logger.info(f"   Batch {batch_num}/{total_batches} ({batch_size_actual} transactions)...")
        if success_count == batch_size_actual:
            logger.info(f"      Batch {batch_num} complete: {success_count} categorized")
        else:
            logger.warning(f"      Batch {batch_num} partial: {success_count}/{batch_size_actual} categorized")

    categorized_count = len(all_results)
    failed_count = total_transactions - categorized_count

    logger.info("Categorization complete")
    logger.info(f"   Successfully categorized: {categorized_count} transactions")
    if failed_count > 0:
        logger.warning(f"   Failed to categorize: {failed_count} transactions")
    logger.info(f"   Success rate: {(categorized_count / total_transactions * 100):.1f}%")

    return all_results


def apply_manual_overrides(db: SprigDatabase, config: Config):
    """Apply manual category overrides from config."""
    if not config.manual_categories:
        return

    valid_category_names = {cat.name for cat in config.categories}

    for manual_cat in config.manual_categories:
        if manual_cat.category not in valid_category_names:
            logger.warning(f"Invalid category '{manual_cat.category}' for {manual_cat.transaction_id}")
            continue
        db.update_transaction_category(manual_cat.transaction_id, manual_cat.category, 1.0)


def categorize_uncategorized_transactions(db: SprigDatabase, config: Config):
    apply_manual_overrides(db, config)

    uncategorized = db.get_uncategorized_transactions()
    transaction_views = [TransactionView.from_db_row(row) for row in uncategorized]

    if not transaction_views:
        return

    results = categorize_in_batches(transaction_views, config)

    for result in results:
        db.update_transaction_category(result.transaction_id, result.category, result.confidence)

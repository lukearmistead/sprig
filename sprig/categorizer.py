"""Transaction categorization using Claude and manual overrides."""

from typing import List

from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from tenacity import retry, stop_after_attempt, wait_exponential

from sprig import credentials
from sprig.logger import get_logger
from sprig.models import TellerTransaction, TransactionCategory, TransactionView, TransactionBatch
from sprig.models.category_config import CategoryConfig

logger = get_logger("sprig.categorizer")


CATEGORIZATION_PROMPT = """Analyze each transaction and assign it to exactly ONE category from the provided list.

AVAILABLE CATEGORIES:
{categories}

TRANSACTIONS TO CATEGORIZE:
{transactions}

TRANSACTION FIELDS:
- description: The transaction description from your bank
- counterparty: The merchant or entity name (when available)
- amount: Transaction amount (negative values are refunds or credits)
- account_name & account_subtype: The account this transaction occurred in (e.g., "credit_card", "checking", "savings")

CATEGORIZATION PROCESS:
1. Read each transaction's description, counterparty (if available), amount, and account type carefully
2. USE ACCOUNT TYPE AS CONTEXT:
   - Credit card transactions are NEVER income (even if negative/refunds)
   - Checking/savings negative amounts may be income (salary, deposits) or refunds
   - Credit card payments from checking → categorize as "loan" or "general" not "income"
3. Look for KEY WORDS that strongly indicate a category:
   - "INSURANCE" + auto/car context → likely vehicle-related
   - "AUTOPAY", "PYMT", "PAYMENT" → likely a transfer or bill payment
   - Gas station names (Shell, Chevron, Pilot, Fast Stop, BP, etc.) → check amount to determine fuel vs. snacks
4. Use transaction amounts as strong hints:
   - Gas stations: $30+ usually fuel, under $15 usually snacks/drinks
   - Pharmacies: $100+ usually prescriptions, under $20 usually personal items
5. HANDLING NEGATIVE AMOUNTS (refunds/credits):
   - Negative amounts are often refunds, NOT income or transfers
   - Categorize refunds based on the merchant/counterparty, not the negative amount
   - Example: A -$50 from REI is a refund for outdoor/sporting goods, not income
   - Example: A -$25 from a restaurant is a dining refund, not a transfer
   - Example: A -$100 on a credit card from Amazon is a return, not income
   - Only categorize as income when clearly salary, deposits, transfers between YOUR accounts
6. Match to the MOST SPECIFIC applicable category based on all available information
7. Avoid over-using "general" - it should be rare. Most transactions have a logical category
8. Only use "undefined" when the merchant and purpose are genuinely unclear
9. CONFIDENCE SCORING (0 to 1):
   - Assign a confidence score to each categorization based on how certain you are
   - High confidence (0.8-1.0): Clear merchant name, obvious category (e.g., "Starbucks" → dining)
   - Medium confidence (0.5-0.79): Some ambiguity but likely correct (e.g., gas station with small amount could be snacks or fuel)
   - Low confidence (0-0.49): Unclear merchant, vague description, or multiple possible categories

CRITICAL REQUIREMENTS:
- You MUST use ONLY the exact category names listed above
- DO NOT create new categories like "personal_care", "education", or "subscriptions"
- If tempted to use a category not in the list, use "general" instead
- Every category in your response MUST match one from AVAILABLE CATEGORIES exactly
- Categorize EVERY transaction (no skipping)

VALIDATION:
Before returning your response, verify that EVERY category you used appears in the AVAILABLE CATEGORIES list above. If not, your response is invalid."""


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


def categorize_manually(
    transactions: List[TellerTransaction],
    category_config: CategoryConfig,
    account_info: dict = None
) -> List[TransactionCategory]:
    """Categorize transactions using manual categories from config.

    Args:
        transactions: List of transactions to categorize
        category_config: CategoryConfig containing manual_categories and valid categories
        account_info: Optional account information (unused, for interface compatibility)

    Returns:
        List of TransactionCategory for manually categorized transactions
    """
    valid_category_names = {cat.name for cat in category_config.categories}
    categorized_transactions = []

    for manual_category in category_config.manual_categories:
        # Validate category
        if manual_category.category not in valid_category_names:
            logger.warning(
                f"Invalid category '{manual_category.category}' for "
                f"{manual_category.transaction_id}, skipping"
            )
            continue

        # Find matching transaction and categorize it
        for txn in transactions:
            if txn.id == manual_category.transaction_id:
                categorized_transactions.append(TransactionCategory(
                    transaction_id=txn.id,
                    category=manual_category.category,
                    confidence=1.0  # Manual categorization always has 100% confidence
                ))

    return categorized_transactions


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    reraise=True,
)
def categorize_inferentially(
    transaction_views: List[TransactionView],
    category_config: CategoryConfig,
) -> List[TransactionCategory]:
    """Categorize transactions using AI agent with exponential backoff retry.

    Args:
        transaction_views: List of TransactionView objects to categorize
        category_config: CategoryConfig containing valid categories

    Returns:
        List of TransactionCategory for categorized transactions

    Raises:
        ValueError: If Claude API key is not configured in keyring
    """
    if not transaction_views:
        return []

    api_key = credentials.get_claude_api_key()
    if not api_key:
        raise ValueError(
            "Claude API key not found in keyring. "
            "Run 'python sprig.py auth' to configure it."
        )

    categories_with_descriptions = [
        f"{cat.name}: {cat.description}" for cat in category_config.categories
    ]

    batch = TransactionBatch(transactions=transaction_views)
    transactions_json = batch.model_dump_json(indent=2)

    prompt = CATEGORIZATION_PROMPT.format(
        categories=", ".join(categories_with_descriptions),
        transactions=transactions_json
    )

    provider = AnthropicProvider(api_key=api_key.value)
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
        if "rate_limit" in error_msg.lower() or "rate limit" in error_msg.lower():
            raise

        return []

    valid_category_names = {cat.name for cat in category_config.categories}
    return _validate_category_results(categories, valid_category_names)


def categorize_in_batches(
    transaction_views: List[TransactionView],
    category_config: CategoryConfig,
    batch_size: int,
) -> List[TransactionCategory]:
    """Categorize transactions in batches with retry logic.

    Args:
        transaction_views: List of TransactionView objects to categorize
        category_config: CategoryConfig containing valid categories
        batch_size: Number of transactions to categorize per API call

    Returns:
        List of TransactionCategory for all categorized transactions
    """
    if not transaction_views:
        return []

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

        results = categorize_inferentially(batch, category_config)
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

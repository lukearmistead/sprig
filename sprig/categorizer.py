"""Transaction categorization using Claude and manual overrides."""

from typing import List

from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider

from sprig import credentials
from sprig.logger import get_logger
from sprig.models import TellerTransaction, TransactionCategory, TransactionView, TransactionBatch
from sprig.models.category_config import CategoryConfig

logger = get_logger("sprig.categorizer")


# Categorization prompt template for AI agent
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


def _build_transaction_views(
    transactions: List[TellerTransaction],
    account_info: dict
) -> List[TransactionView]:
    """Build transaction views with account context for categorization.

    Args:
        transactions: List of transactions to build views for
        account_info: Account information keyed by transaction ID

    Returns:
        List of TransactionView objects with account context
    """
    views = []
    for t in transactions:
        info = account_info.get(t.id, {})
        views.append(
            TransactionView(
                id=t.id,
                date=str(t.date),
                description=t.description,
                amount=t.amount,
                inferred_category=None,
                counterparty=info.get('counterparty'),
                account_name=info.get('name'),
                account_subtype=info.get('subtype'),
                account_last_four=info.get('last_four')
            )
        )
    return views


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


def categorize_inferentially(
    transactions: List[TellerTransaction],
    category_config: CategoryConfig,
    account_info: dict = None
) -> List[TransactionCategory]:
    """Categorize transactions using AI agent.

    Args:
        transactions: List of transactions to categorize
        category_config: CategoryConfig containing valid categories
        account_info: Optional account information for context

    Returns:
        List of TransactionCategory for categorized transactions

    Raises:
        ValueError: If Claude API key is not configured in keyring
    """
    if not transactions:
        return []

    account_info = account_info or {}

    api_key = credentials.get_claude_api_key()
    if not api_key:
        raise ValueError(
            "Claude API key not found in keyring. "
            "Run 'python sprig.py auth' to configure it."
        )

    categories_with_descriptions = [
        f"{cat.name}: {cat.description}" for cat in category_config.categories
    ]

    transaction_views = _build_transaction_views(transactions, account_info)
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
        categories = result.data
    except Exception as e:
        logger.error(f"Failed to categorize transactions: {e}")
        return []

    valid_category_names = {cat.name for cat in category_config.categories}
    return _validate_category_results(categories, valid_category_names)

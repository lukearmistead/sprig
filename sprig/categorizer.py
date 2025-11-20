"""Transaction categorization using Claude."""

import time
from typing import List

import anthropic

from sprig.logger import get_logger
from sprig.models import RuntimeConfig, TellerTransaction, ClaudeResponse, TransactionCategory, TransactionView
from sprig.models.category_config import CategoryConfig

logger = get_logger("sprig.categorizer")

PROMPT_TEMPLATE = """Analyze each transaction and assign it to exactly ONE category from the provided list.

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

CRITICAL REQUIREMENTS:
- You MUST use ONLY the exact category names listed above
- DO NOT create new categories like "personal_care", "education", or "subscriptions"
- If tempted to use a category not in the list, use "general" instead
- Every category in your response MUST match one from AVAILABLE CATEGORIES exactly
- Categorize EVERY transaction (no skipping)
- Return ONLY the JSON output, no explanations

VALIDATION:
Before returning your response, verify that EVERY category you used appears in the AVAILABLE CATEGORIES list above. If not, your response is invalid.

OUTPUT FORMAT:
[
  {{"transaction_id": "txn_example1", "category": "category_name"}},
  {{"transaction_id": "txn_example2", "category": "category_name"}}
]"""


def build_categorization_prompt(
    transactions: List[TellerTransaction],
    account_info: dict,
    category_config: CategoryConfig,
    prompt_template: str = PROMPT_TEMPLATE
) -> str:
    """Build the categorization prompt with category descriptions.

    Args:
        transactions: List of transactions to categorize
        account_info: Dictionary mapping transaction IDs to account name/subtype
        category_config: CategoryConfig with all category data
        prompt_template: Template string with {categories} and {transactions} placeholders

    Returns:
        Formatted prompt string
    """
    # Format categories with descriptions: "name: description"
    categories_with_descriptions = [f"{cat.name}: {cat.description}" for cat in category_config.categories]

    # Convert to minimal format for LLM
    minimal_transactions = []
    for t in transactions:
        info = account_info.get(t.id, {})
        minimal_transactions.append(
            TransactionView(
                id=t.id,
                date=str(t.date),
                description=t.description,
                amount=t.amount,
                inferred_category=None,  # Not yet categorized
                counterparty=info.get('counterparty'),
                account_name=info.get('name'),
                account_subtype=info.get('subtype'),
                account_last_four=info.get('last_four')
            )
        )

    # Use Pydantic's built-in JSON serialization for the minimal list
    from pydantic import TypeAdapter
    transactions_adapter = TypeAdapter(List[TransactionView])
    transactions_json = transactions_adapter.dump_json(minimal_transactions, indent=2).decode()

    return prompt_template.format(
        categories=", ".join(categories_with_descriptions),
        transactions=transactions_json
    )


class TransactionCategorizer:
    """Claude-based transaction categorization."""

    def __init__(self, runtime_config: RuntimeConfig):
        self.runtime_config = runtime_config
        self.category_config = CategoryConfig.load()
        self.client = anthropic.Anthropic(api_key=runtime_config.claude_api_key)

    def categorize_batch(self, transactions: List[TellerTransaction], account_info: dict = None) -> dict:
        """Categorize a batch of transactions using Claude with retry logic."""
        max_retries = 3

        for attempt in range(max_retries):
            try:
                return self._attempt_categorization(transactions, account_info or {})
            except Exception as e:
                error_str = str(e)
                
                # Check if this is a rate limit error
                if "rate_limit_error" in error_str or "rate limit" in error_str.lower():
                    if attempt == 0:  # First time seeing rate limit
                        logger.warning("⏳ Hit Claude API rate limit - this is normal with large transaction volumes")
                        logger.info("   💡 Tip: Use '--days N' flag to sync fewer transactions and reduce API costs")
                        logger.info("   💡 Or run sync multiple times to process transactions in chunks")
                    
                    if attempt < max_retries - 1:
                        # Much longer delays for rate limits (60, 120 seconds)
                        delay = 60 * (2 ** attempt)
                        logger.info(f"   ⏱️  Waiting {delay} seconds for rate limit to reset...")
                        time.sleep(delay)
                    else:
                        logger.error(f"   ❌ Still hitting rate limits after {max_retries} attempts")
                        logger.info("   💡 Try running sync again later, or use '--days 7' to sync recent transactions only")
                        raise e  # Re-raise to stop categorization entirely
                else:
                    # Non-rate-limit errors (API errors, network issues, etc.)
                    logger.error(f"Batch categorization failed (attempt {attempt + 1}/{max_retries}): {e}")
                    
                    if attempt < max_retries - 1:
                        delay = 2 ** attempt  # Normal exponential backoff: 1s, 2s
                        logger.info(f"Retrying in {delay} seconds...")
                        time.sleep(delay)
                    else:
                        logger.error(f"Failed after {max_retries} attempts, skipping this batch")

        return {}

    def _attempt_categorization(self, transactions: List[TellerTransaction], account_info: dict) -> dict:
        """Single attempt at categorizing a batch."""
        full_prompt = build_categorization_prompt(transactions, account_info, self.category_config)

        response = self.client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1000,
            messages=[
                {"role": "user", "content": full_prompt},
                {"role": "assistant", "content": "["}
            ]
        )

        claude_response = ClaudeResponse(**response.model_dump())
        json_text = claude_response.text

        # Parse JSON string using Pydantic's built-in validation
        # Note: Claude returns partial JSON (missing opening [) because we pre-fill it
        try:
            from pydantic import TypeAdapter
            complete_json = "[" + json_text
            categories_adapter = TypeAdapter(List[TransactionCategory])
            categories_list = categories_adapter.validate_json(complete_json)
        except Exception as e:
            logger.error(f"Failed to parse Claude response as JSON: {e}")
            logger.error(f"Raw response: {json_text[:200]}...")
            raise e

        return self._validate_categories(categories_list)

    def _validate_categories(self, categories_list: List[TransactionCategory]) -> dict:
        """Validate Claude's categorization response against allowed categories."""
        # Pydantic has already converted these to TransactionCategory objects

        # Validate categories and set to None if invalid
        valid_names = {cat.name for cat in self.category_config.categories}
        validated = {}
        for item in categories_list:
            if item.category in valid_names:
                validated[item.transaction_id] = item.category
            else:
                logger.warning(f"Invalid category '{item.category}' for {item.transaction_id}, setting to None")
                validated[item.transaction_id] = None

        return validated
"""Transaction categorization using Claude and manual overrides."""

import time
from typing import List

import anthropic
from pydantic import TypeAdapter

from sprig.logger import get_logger
from sprig.models import TellerTransaction, ClaudeResponse, TransactionCategory, TransactionView
from sprig.models.category_config import CategoryConfig
import sprig.credentials as credentials

logger = get_logger("sprig.categorizer")


class ManualCategorizer:
    """Applies manual categorization from config."""

    CONFIDENCE = 1.0

    def __init__(self, category_config: CategoryConfig):
        """Initialize with category configuration.

        Args:
            category_config: CategoryConfig containing manual_categories
        """
        self.category_config = category_config
        self.valid_category_names = {cat.name for cat in category_config.categories}

    def categorize_batch(self, transactions: List[TellerTransaction], account_info: dict = None) -> List[TransactionCategory]:
        """Categorize transactions using manual categories from config.

        Args:
            transactions: List of transactions to categorize
            account_info: Unused, for interface compatibility with ClaudeCategorizer

        Returns:
            List of TransactionCategory for manually categorized transactions
        """
        categorized_transactions = []
        for manual_category in self.category_config.manual_categories:
            if not self._validate_category(manual_category.category):
                logger.warning(f"Invalid category '{manual_category.category}' for {manual_category.transaction_id}, skipping")
                continue
            for txn in transactions:
                if txn.id == manual_category.transaction_id:
                    categorized_transactions.append(TransactionCategory(
                        transaction_id=txn.id,
                        category=manual_category.category,
                        confidence=self.CONFIDENCE
                    ))
        return categorized_transactions

    def _validate_category(self, category: str) -> bool:
        """Check if a category is valid.

        Args:
            category: Category name to validate

        Returns:
            True if category is valid, False otherwise
        """
        return category in self.valid_category_names


class ClaudeCategorizer:
    """Claude-based transaction categorization."""

    MAX_RETRIES = 3
    RATE_LIMIT_BASE_DELAY = 60
    BACKOFF_BASE_DELAY = 1
    MODEL = "claude-haiku-4-5-20251001"
    MAX_TOKENS = 1000

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
- Return ONLY the JSON output, no explanations

VALIDATION:
Before returning your response, verify that EVERY category you used appears in the AVAILABLE CATEGORIES list above. If not, your response is invalid.

OUTPUT FORMAT:
[
  {{"transaction_id": "txn_example1", "category": "category_name", "confidence": 0.95}},
  {{"transaction_id": "txn_example2", "category": "category_name", "confidence": 0.60}}
]"""

    def __init__(self, category_config: CategoryConfig):
        """Initialize with category configuration.

        Args:
            category_config: CategoryConfig containing categories
        """
        self.category_config = category_config
        self.valid_category_names = {cat.name for cat in category_config.categories}
        api_key = credentials.get_claude_api_key()
        if not api_key:
            raise ValueError("Claude API key not found in keyring")
        self.client = anthropic.Anthropic(api_key=api_key.value)

    def _build_prompt(self, transactions: List[TellerTransaction], account_info: dict) -> str:
        """Build the categorization prompt with category descriptions.

        Args:
            transactions: List of transactions to categorize
            account_info: Dictionary mapping transaction IDs to account name/subtype

        Returns:
            Formatted prompt string
        """
        categories_with_descriptions = [
            f"{cat.name}: {cat.description}" for cat in self.category_config.categories
        ]

        minimal_transactions = []
        for t in transactions:
            info = account_info.get(t.id, {})
            minimal_transactions.append(
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

        transactions_adapter = TypeAdapter(List[TransactionView])
        transactions_json = transactions_adapter.dump_json(minimal_transactions, indent=2).decode()

        return self.PROMPT_TEMPLATE.format(
            categories=", ".join(categories_with_descriptions),
            transactions=transactions_json
        )

    def categorize_batch(self, transactions: List[TellerTransaction], account_info: dict = None) -> List[TransactionCategory]:
        """Categorize a batch of transactions using Claude with retry logic."""
        for attempt in range(self.MAX_RETRIES):
            try:
                return self._attempt_categorization(transactions, account_info or {})
            except Exception as e:
                is_rate_limit = self._is_rate_limit_error(e)
                is_last_attempt = attempt >= self.MAX_RETRIES - 1

                if is_rate_limit:
                    self._log_rate_limit_error(attempt, is_last_attempt)
                else:
                    self._log_general_error(e, attempt, is_last_attempt)

                if is_last_attempt:
                    if is_rate_limit:
                        raise e
                    return []

                delay = self._get_retry_delay(attempt, is_rate_limit)
                time.sleep(delay)

        return []

    def _attempt_categorization(self, transactions: List[TellerTransaction], account_info: dict) -> List[TransactionCategory]:
        """Single attempt at categorizing a batch."""
        full_prompt = self._build_prompt(transactions, account_info)

        response = self.client.messages.create(
            model=self.MODEL,
            max_tokens=self.MAX_TOKENS,
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
            complete_json = "[" + json_text
            categories_adapter = TypeAdapter(List[TransactionCategory])
            categories = categories_adapter.validate_json(complete_json)
        except Exception as e:
            logger.error(f"Failed to parse Claude response as JSON: {e}")
            logger.error(f"Raw response: {json_text[:200]}...")
            raise e

        return self._validate_categories(categories)

    def _validate_category(self, category: str) -> bool:
        """Check if a category is valid.

        Args:
            category: Category name to validate

        Returns:
            True if category is valid, False otherwise
        """
        return category in self.valid_category_names

    def _validate_categories(self, categories: List[TransactionCategory]) -> List[TransactionCategory]:
        """Filter out invalid categories from the list.

        Args:
            categories: List of TransactionCategory objects to validate

        Returns:
            List containing only valid categories
        """
        validated = []
        for category in categories:
            if self._validate_category(category.category):
                validated.append(category)
            else:
                logger.warning(f"Invalid category '{category.category}' for {category.transaction_id}, skipping")
        return validated

    def _is_rate_limit_error(self, error: Exception) -> bool:
        """Check if an error is a rate limit error."""
        error_str = str(error)
        return "rate_limit_error" in error_str or "rate limit" in error_str.lower()

    def _get_retry_delay(self, attempt: int, is_rate_limit: bool) -> int:
        """Calculate retry delay based on attempt number and error type."""
        if is_rate_limit:
            return self.RATE_LIMIT_BASE_DELAY * (2 ** attempt)
        return self.BACKOFF_BASE_DELAY * (2 ** attempt)

    def _log_rate_limit_error(self, attempt: int, is_last_attempt: bool) -> None:
        """Log rate limit error with helpful tips."""
        if attempt == 0:
            logger.warning("Hit Claude API rate limit - this is normal with large transaction volumes")
            logger.info("   Tip: Use '--days N' flag to sync fewer transactions and reduce API costs")
            logger.info("   Or run sync multiple times to process transactions in chunks")

        if is_last_attempt:
            logger.error(f"Still hitting rate limits after {self.MAX_RETRIES} attempts")
            logger.info("   Try running sync again later, or use '--days 7' to sync recent transactions only")
        else:
            delay = self._get_retry_delay(attempt, is_rate_limit=True)
            logger.info(f"   Waiting {delay} seconds for rate limit to reset...")

    def _log_general_error(self, error: Exception, attempt: int, is_last_attempt: bool) -> None:
        """Log general categorization error."""
        logger.error(f"Batch categorization failed (attempt {attempt + 1}/{self.MAX_RETRIES}): {error}")
        if is_last_attempt:
            logger.error(f"Failed after {self.MAX_RETRIES} attempts, skipping this batch")
        else:
            delay = self._get_retry_delay(attempt, is_rate_limit=False)
            logger.info(f"Retrying in {delay} seconds...")
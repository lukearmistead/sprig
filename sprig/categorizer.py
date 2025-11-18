"""Transaction categorization using Claude."""

import time
from typing import List

import anthropic

from sprig.models import RuntimeConfig, TellerTransaction, ClaudeResponse, TransactionCategory
from sprig.models.category_config import CategoryConfig

FALLBACK_CATEGORY = "undefined"
PROMPT_TEMPLATE = """Analyze each transaction and assign it to exactly ONE category from the provided list.

AVAILABLE CATEGORIES:
{categories}

TRANSACTIONS TO CATEGORIZE:
{transactions}

CATEGORIZATION PROCESS:
1. Read each transaction's description, merchant name, and amount carefully
2. Look for KEY WORDS that strongly indicate a category:
   - "INSURANCE" + auto/car context → likely vehicle-related
   - "AUTOPAY", "PYMT", "PAYMENT" → likely a transfer or bill payment
   - Gas station names (Shell, Chevron, Pilot, BP, etc.) → check amount to determine fuel vs. snacks
3. Use transaction amounts as strong hints:
   - Gas stations: $30+ usually fuel, under $15 usually snacks/drinks
   - Pharmacies: $100+ usually prescriptions, under $20 usually personal items
4. Match to the MOST SPECIFIC applicable category based on all available information
5. Avoid over-using "general" - it should be rare. Most transactions have a logical category
6. Only use "undefined" when the merchant and purpose are genuinely unclear

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
    category_config: CategoryConfig,
    prompt_template: str = PROMPT_TEMPLATE
) -> str:
    """Build the categorization prompt with category descriptions.

    Args:
        transactions: List of transactions to categorize
        category_config: CategoryConfig with all category data
        prompt_template: Template string with {categories} and {transactions} placeholders

    Returns:
        Formatted prompt string
    """
    # Format categories with descriptions: "name: description"
    categories_with_descriptions = [f"{cat.name}: {cat.description}" for cat in category_config.categories]

    # Use Pydantic's built-in JSON serialization for the entire list
    from pydantic import TypeAdapter
    transactions_adapter = TypeAdapter(List[TellerTransaction])
    transactions_json = transactions_adapter.dump_json(transactions, indent=2).decode()

    return prompt_template.format(
        categories=", ".join(categories_with_descriptions),
        transactions=transactions_json
    )


class TransactionCategorizer:
    """Claude-based transaction categorization."""

    def __init__(self, runtime_config: RuntimeConfig, fallback_category: str = FALLBACK_CATEGORY):
        self.runtime_config = runtime_config
        self.category_config = CategoryConfig.load()
        self.client = anthropic.Anthropic(api_key=runtime_config.claude_api_key)
        self.fallback_category = fallback_category

    def categorize_batch(self, transactions: List[TellerTransaction]) -> dict:
        """Categorize a batch of transactions using Claude with retry logic."""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                return self._attempt_categorization(transactions)
            except Exception as e:
                print(f"ERROR: Batch categorization failed (attempt {attempt + 1}/{max_retries}): {e}")
                
                if attempt < max_retries - 1:
                    delay = 2 ** attempt  # Exponential backoff: 1s, 2s
                    print(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    print(f"Failed after {max_retries} attempts, skipping this batch")
        
        return {}

    def _attempt_categorization(self, transactions: List[TellerTransaction]) -> dict:
        """Single attempt at categorizing a batch."""
        full_prompt = build_categorization_prompt(transactions, self.category_config)

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
            print(f"ERROR: Failed to parse Claude response as JSON: {e}")
            print(f"Raw response: {json_text[:200]}...")
            raise e

        return self._validate_categories(categories_list)

    def _validate_categories(self, categories_list: List[TransactionCategory]) -> dict:
        """Validate Claude's categorization response against allowed categories."""
        # Pydantic has already converted these to TransactionCategory objects

        # Validate categories and apply fallback
        valid_names = {cat.name for cat in self.category_config.categories}
        validated = {}
        for item in categories_list:
            if item.category in valid_names:
                validated[item.transaction_id] = item.category
            else:
                print(f"Warning: Invalid category '{item.category}' for {item.transaction_id}, using '{self.fallback_category}'")
                validated[item.transaction_id] = self.fallback_category

        return validated

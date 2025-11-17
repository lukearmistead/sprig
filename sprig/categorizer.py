"""Transaction categorization using Claude."""

from typing import List

import anthropic

from sprig.models import RuntimeConfig, TellerTransaction, ClaudeResponse, TransactionCategory
from sprig.models.category_config import CategoryConfig

FALLBACK_CATEGORY = "undefined"
PROMPT_TEMPLATE = """Categorize these financial transactions into the most appropriate category.

IMPORTANT: You must use ONLY these exact categories, no others: {categories}

Transactions to categorize:
{transactions}

Return a JSON array of objects with transaction_id and category fields. For example:
[{{"transaction_id": "txn_123", "category": "groceries"}}, {{"transaction_id": "txn_456", "category": "dining"}}]

Guidelines:
- Use "groceries" for food stores and supermarkets
- Use "dining" for restaurants and food delivery
- Use "fuel" for gas stations
- Use "transport" or "transportation" for travel
- Use "general" for miscellaneous items that don't fit other categories
- You MUST only use categories from the list above

Return only the JSON array, no other text."""




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
        """Categorize a batch of transactions using Claude."""
        full_prompt = build_categorization_prompt(transactions, self.category_config)

        response = self.client.messages.create(
            model="claude-3-haiku-20240307",
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
        except Exception:
            categories_list = []
        
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

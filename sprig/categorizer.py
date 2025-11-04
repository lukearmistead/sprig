"""Transaction categorization using Claude."""

import json
from typing import Dict, List

import anthropic

import yaml
from pathlib import Path

from sprig.models import RuntimeConfig, TellerTransaction, ClaudeResponse, TransactionCategory

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


def load_categories(config_path: Path = None) -> Dict[str, str]:
    """Load category definitions from YAML file.

    Returns:
        Dict mapping category names to descriptions
    """
    config_path = config_path or Path(__file__).parent.parent / "config.yml"

    with open(config_path, 'r') as f:
        config_data = yaml.safe_load(f)

    # Simple validation - ensure we have a categories dict
    if not isinstance(config_data, dict) or 'categories' not in config_data:
        raise ValueError("config.yml must contain a 'categories' section")

    categories = config_data['categories']

    # Ensure all values are strings
    if not all(isinstance(desc, str) for desc in categories.values()):
        raise ValueError("All category descriptions must be strings")

    return categories


def get_category_names(categories: Dict[str, str] = None) -> List[str]:
    """Get list of all category names.

    Args:
        categories: Optional category dict, loads from config if not provided

    Returns:
        List of category names
    """
    if categories is None:
        categories = load_categories()
    return list(categories.keys())


def build_categorization_prompt(
    transactions: List[TellerTransaction],
    categories: Dict[str, str],
    prompt_template: str = PROMPT_TEMPLATE
) -> str:
    """Build the categorization prompt with category descriptions.

    Args:
        transactions: List of transactions to categorize
        categories: Dict mapping category names to descriptions
        prompt_template: Template string with {categories} and {transactions} placeholders

    Returns:
        Formatted prompt string
    """
    transaction_data = [txn.model_dump() for txn in transactions]
    # Format categories with descriptions: "name: description"
    categories_with_descriptions = [f"{name}: {desc}" for name, desc in categories.items()]

    return prompt_template.format(
        categories=", ".join(categories_with_descriptions),
        transactions=json.dumps(transaction_data, indent=2, default=str)
    )


class TransactionCategorizer:
    """Claude-based transaction categorization."""

    def __init__(self, runtime_config: RuntimeConfig, fallback_category: str = FALLBACK_CATEGORY):
        self.runtime_config = runtime_config
        self.categories = load_categories()
        self.client = anthropic.Anthropic(api_key=runtime_config.claude_api_key)
        self.fallback_category = fallback_category

    def categorize_batch(self, transactions: List[TellerTransaction]) -> dict:
        """Categorize a batch of transactions using Claude."""
        full_prompt = build_categorization_prompt(transactions, self.categories)

        response = self.client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1000,
            messages=[
                {"role": "user", "content": full_prompt},
                {"role": "assistant", "content": "["}
            ]
        )

        claude_response = ClaudeResponse(**response.model_dump())
        categories_list = claude_response.text
        return self._validate_categories(categories_list)

    def _validate_categories(self, categories_list: List[TransactionCategory]) -> dict:
        """Validate Claude's categorization response against allowed categories."""
        # Pydantic has already converted these to TransactionCategory objects

        # Validate categories and apply fallback
        valid_names = set(self.categories.keys())
        validated = {}
        for item in categories_list:
            if item.category in valid_names:
                validated[item.transaction_id] = item.category
            else:
                print(f"Warning: Invalid category '{item.category}' for {item.transaction_id}, using '{self.fallback_category}'")
                validated[item.transaction_id] = self.fallback_category

        return validated

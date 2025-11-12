"""Transaction categorization using Claude."""

from typing import Dict, List

import anthropic

from sprig.models import RuntimeConfig, TellerTransaction, ClaudeResponse, TransactionCategory
from sprig.prompt_catalog import PromptCatalog

FALLBACK_CATEGORY = "undefined"


class TransactionCategorizer:
    """Claude-based transaction categorization."""

    def __init__(self, runtime_config: RuntimeConfig, fallback_category: str = FALLBACK_CATEGORY):
        self.runtime_config = runtime_config
        self.prompt_catalog = PromptCatalog()
        self.client = anthropic.Anthropic(api_key=runtime_config.claude_api_key)
        self.fallback_category = fallback_category

    def categorize_batch(self, transactions: List[TellerTransaction]) -> dict:
        """Categorize a batch of transactions using Claude."""
        prompt_config = self.prompt_catalog.get_prompt("categorization")
        
        full_prompt = self.prompt_catalog.render_template(
            "categorization",
            categories=self.prompt_catalog.format_categories(),
            transactions=self.prompt_catalog.format_transactions(transactions)
        )

        response = self.client.messages.create(
            model=prompt_config.model,
            max_tokens=prompt_config.max_tokens,
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

        # Get valid categories from the catalog
        valid_names = set(self.prompt_catalog._categories.keys())
        validated = {}
        for item in categories_list:
            if item.category in valid_names:
                validated[item.transaction_id] = item.category
            else:
                print(f"Warning: Invalid category '{item.category}' for {item.transaction_id}, using '{self.fallback_category}'")
                validated[item.transaction_id] = self.fallback_category

        return validated

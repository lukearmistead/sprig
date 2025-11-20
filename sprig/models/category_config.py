"""Category configuration models for Sprig."""

from pathlib import Path
from typing import List

import yaml
from pydantic import BaseModel, model_validator


class Category(BaseModel):
    """Individual transaction category."""
    name: str
    description: str


class CategoryOverride(BaseModel):
    """Category override for a specific transaction."""
    transaction_id: str
    category: str


class CategoryConfig(BaseModel):
    """Transaction category configuration from config.yml."""
    categories: List[Category]
    manual_categories: List[CategoryOverride] = []

    @model_validator(mode='after')
    def validate_override_categories(self):
        """Validate that override categories match valid category names."""
        if not self.manual_categories:
            return self

        valid_categories = {cat.name for cat in self.categories}
        invalid_overrides = [
            override for override in self.manual_categories
            if override.category not in valid_categories
        ]

        if invalid_overrides:
            invalid_items = [
                f"{override.transaction_id} -> '{override.category}'"
                for override in invalid_overrides
            ]
            raise ValueError(
                f"Invalid categories in overrides: {', '.join(invalid_items)}. "
                f"Valid categories: {', '.join(sorted(valid_categories))}"
            )

        return self

    @classmethod
    def load(cls, config_path: Path = None):
        """Load category configuration from YAML file."""
        config_path = config_path or Path(__file__).parent.parent.parent / "config.yml"

        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)

        return cls(**config_data)
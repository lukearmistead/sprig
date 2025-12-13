"""Category configuration models for Sprig."""

from pathlib import Path
from typing import List

import yaml
from pydantic import BaseModel, model_validator


class Category(BaseModel):
    """Individual transaction category."""
    name: str
    description: str


class ManualCategory(BaseModel):
    """Manual categorization for a specific transaction."""
    transaction_id: str
    category: str


class CategoryConfig(BaseModel):
    """Transaction category configuration from config.yml."""
    categories: List[Category]
    manual_categories: List[ManualCategory] = []
    batch_size: int = 25

    @model_validator(mode='after')
    def validate_manual_categories(self):
        """Validate that manual categories match valid category names."""
        if not self.manual_categories:
            return self

        valid_categories = {cat.name for cat in self.categories}
        invalid_manual_cats = [
            manual_cat for manual_cat in self.manual_categories
            if manual_cat.category not in valid_categories
        ]

        if invalid_manual_cats:
            invalid_items = [
                f"{manual_cat.transaction_id} -> '{manual_cat.category}'"
                for manual_cat in invalid_manual_cats
            ]
            raise ValueError(
                f"Invalid categories in manual_categories: {', '.join(invalid_items)}. "
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
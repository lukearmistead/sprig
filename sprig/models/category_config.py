"""Category configuration models for Sprig."""

from pathlib import Path
from typing import List

import yaml
from pydantic import BaseModel, field_validator


class Category(BaseModel):
    """Individual transaction category."""
    name: str
    description: str


class ManualOverride(BaseModel):
    """Manual category override for a specific transaction."""
    transaction_id: str
    category: str


class CategoryConfig(BaseModel):
    """Transaction category configuration from config.yml."""
    categories: List[Category]
    manual_overrides: List[ManualOverride] = []

    @field_validator('manual_overrides')
    @classmethod
    def validate_override_categories(cls, overrides, info):
        """Validate that override categories match valid category names."""
        if not overrides:
            return overrides

        # Get valid category names from the data being validated
        categories = info.data.get('categories', [])
        valid_categories = {cat.name for cat in categories}

        # Validate each override
        for override in overrides:
            if override.category not in valid_categories:
                raise ValueError(
                    f"Invalid category '{override.category}' in manual override for "
                    f"transaction '{override.transaction_id}'. Valid categories: {', '.join(sorted(valid_categories))}"
                )

        return overrides

    @classmethod
    def load(cls, config_path: Path = None):
        """Load category configuration from YAML file."""
        config_path = config_path or Path(__file__).parent.parent.parent / "config.yml"

        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)

        return cls(**config_data)
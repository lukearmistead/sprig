"""Category configuration models for Sprig."""

from pathlib import Path
from typing import List

import yaml
from pydantic import BaseModel


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

    @classmethod
    def load(cls, config_path: Path = None):
        """Load category configuration from YAML file."""
        config_path = config_path or Path(__file__).parent.parent.parent / "config.yml"

        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)

        return cls(**config_data)
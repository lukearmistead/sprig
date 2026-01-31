"""Configuration models for Sprig."""

import shutil
import sys
from datetime import date
from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel

from sprig.paths import get_default_config_path


class Category(BaseModel):
    """Individual transaction category."""
    name: str
    description: str


class ManualCategory(BaseModel):
    """Manual categorization for a specific transaction."""
    transaction_id: str
    category: str


class Config(BaseModel):
    """Application configuration from config.yml."""
    categories: List[Category]
    manual_categories: List[ManualCategory] = []
    batch_size: int = 10
    from_date: Optional[date] = None

    @classmethod
    def _get_bundled_config(cls) -> Path | None:
        """Find bundled config.yml in PyInstaller bundle or repo root."""
        if getattr(sys, 'frozen', False):
            bundled = Path(sys._MEIPASS) / "config.yml"
        else:
            bundled = Path(__file__).parent.parent.parent / "config.yml"
        return bundled if bundled.exists() else None

    @classmethod
    def load(cls, config_path: Path = None):
        """Load category configuration from YAML file, or return defaults."""
        config_path = config_path or get_default_config_path()

        if not config_path.exists():
            bundled = cls._get_bundled_config()
            if bundled:
                shutil.copy(bundled, config_path)
            else:
                return cls(categories=[])

        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)

        return cls(**config_data)
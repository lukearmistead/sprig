"""Configuration models for Sprig."""

import shutil
from datetime import date
from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel

from sprig.paths import is_frozen, get_default_config_path


class Category(BaseModel):
    name: str
    description: str


class ManualCategory(BaseModel):
    transaction_id: str
    category: str


class Config(BaseModel):
    categories: List[Category]
    manual_categories: List[ManualCategory] = []
    batch_size: int
    from_date: Optional[date] = None
    app_id: str = ""
    claude_key: str = ""
    access_tokens: List[str] = []
    environment: str = ""
    cert_path: str = ""
    key_path: str = ""

    @classmethod
    def load(cls, config_path: Path = None) -> "Config":
        config_path = config_path or get_default_config_path()

        if not config_path.exists():
            bundled = cls._bundled_config_path()
            if bundled and bundled.exists():
                config_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(bundled, config_path)

        with open(config_path, "r") as f:
            config_data = yaml.safe_load(f)

        return cls(**config_data)

    @staticmethod
    def _bundled_config_path() -> Optional[Path]:
        import sys

        if is_frozen():
            return Path(sys._MEIPASS) / "config.yml"
        return Path(__file__).parent.parent.parent / "config.yml"

    def save_credentials(self, config_path: Path = None):
        config_path = config_path or get_default_config_path()
        with open(config_path, "r") as f:
            raw = yaml.safe_load(f)
        raw["access_tokens"] = self.access_tokens
        raw["app_id"] = self.app_id
        raw["claude_key"] = self.claude_key
        raw["environment"] = self.environment
        raw["cert_path"] = self.cert_path
        raw["key_path"] = self.key_path
        with open(config_path, "w") as f:
            yaml.dump(raw, f, default_flow_style=False, sort_keys=False)

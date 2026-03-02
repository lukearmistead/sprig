"""Configuration models for Sprig."""

import shutil
import sys
from datetime import date
from pathlib import Path
from typing import List, Optional

from ruamel.yaml import YAML
from pydantic import BaseModel, field_validator

from sprig.paths import get_default_config_path, get_default_certs_dir


class Category(BaseModel):
    name: str
    description: str


class ManualCategory(BaseModel):
    transaction_id: str
    category: str


class Config(BaseModel):
    categories: List[Category]
    manual_categories: List[ManualCategory] = []
    batch_size: int = 50
    from_date: Optional[date] = None
    app_id: str = ""
    claude_key: str = ""
    access_tokens: List[str] = []
    environment: str = "development"
    cert_path: str = ""
    key_path: str = ""
    categorization_prompt: str = ""

    @field_validator("from_date", mode="before")
    @classmethod
    def empty_string_to_none(cls, v):
        if v == "":
            return None
        return v



def _bundled_config_path() -> Optional[Path]:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "config-template.yml"
    return Path(__file__).parent.parent.parent / "config-template.yml"


def _ensure_config_exists(config_path: Path):
    if config_path.exists():
        return
    bundled = _bundled_config_path()
    if bundled and bundled.exists():
        config_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bundled, config_path)
        get_default_certs_dir()  # First run: create certs dir alongside config


def load_config(config_path: Path = None) -> Config:
    config_path = config_path or get_default_config_path()
    _ensure_config_exists(config_path)
    yml = YAML()
    with open(config_path, "r") as f:
        return Config(**yml.load(f))

"""Runtime configuration loading for Sprig."""

import os
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator


class RuntimeConfig(BaseModel):
    """Runtime configuration for Sprig (API keys, paths, certificates)."""

    app_id: str = Field(..., min_length=1)
    access_tokens: List[str] = Field(..., min_length=1)
    claude_api_key: str = Field(..., min_length=1)
    environment: str = "development"
    cert_path: Path
    key_path: Path
    database_path: Path = Path("sprig.db")

    @field_validator('cert_path', 'key_path')
    @classmethod
    def validate_file_exists(cls, v: Path) -> Path:
        if not v.exists():
            raise ValueError(f"File does not exist: {v}")
        return v

    @classmethod
    def load(cls):
        """Load configuration from .env file."""
        project_root = Path(__file__).parent.parent.parent
        load_dotenv(project_root / ".env")

        return cls(
            app_id=os.getenv("APP_ID"),
            access_tokens=[token for token in os.getenv("ACCESS_TOKENS").split(",") if token],
            claude_api_key=os.getenv("CLAUDE_API_KEY"),
            environment=os.getenv("ENVIRONMENT", "development"),
            cert_path=project_root / os.getenv("CERT_PATH"),
            key_path=project_root / os.getenv("KEY_PATH"),
            database_path=project_root / os.getenv("DATABASE_PATH", "sprig.db"),
        )
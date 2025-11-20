"""Runtime configuration loading for Sprig."""

import os
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

from sprig import credential_manager


class TellerAccessToken(BaseModel):
    """Validated Teller access token."""
    token: str = Field(..., pattern=r'^token_[a-z0-9]{26}$', description="Teller access tokens start with 'token_' followed by exactly 26 lowercase alphanumeric characters")


class RuntimeConfig(BaseModel):
    """Runtime configuration for Sprig (API keys, paths, certificates)."""

    app_id: str = Field(..., pattern=r'^app_[a-z0-9]{21}$', description="Teller APP_ID should start with 'app_' followed by exactly 21 lowercase alphanumeric characters")
    access_tokens: List[TellerAccessToken] = Field(..., min_length=1)
    claude_api_key: str = Field(..., pattern=r'^sk-ant-api03-[A-Za-z0-9\-]{95}$', description="Claude API keys start with 'sk-ant-api03-' followed by exactly 95 alphanumeric characters and dashes")
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
        """
        Load configuration from keyring or .env file.

        Credentials are loaded from the system keyring first, with fallback
        to .env file for backward compatibility.
        """
        project_root = Path(__file__).parent.parent.parent

        # Load .env file as fallback (credential_manager will use it if keyring is empty)
        load_dotenv(project_root / ".env")

        # Get credentials from keyring (with .env fallback)
        app_id = credential_manager.get_credential(credential_manager.KEY_APP_ID, fallback_to_env=True)
        access_tokens_str = credential_manager.get_credential(credential_manager.KEY_ACCESS_TOKENS, fallback_to_env=True)
        claude_api_key = credential_manager.get_credential(credential_manager.KEY_CLAUDE_API_KEY, fallback_to_env=True)
        environment = credential_manager.get_credential(credential_manager.KEY_ENVIRONMENT, fallback_to_env=True) or "development"
        cert_path_str = credential_manager.get_credential(credential_manager.KEY_CERT_PATH, fallback_to_env=True)
        key_path_str = credential_manager.get_credential(credential_manager.KEY_KEY_PATH, fallback_to_env=True)
        database_path_str = credential_manager.get_credential(credential_manager.KEY_DATABASE_PATH, fallback_to_env=True) or "sprig.db"

        # Parse access tokens
        access_tokens = []
        if access_tokens_str:
            access_tokens = [TellerAccessToken(token=token) for token in access_tokens_str.split(",") if token]

        return cls(
            app_id=app_id,
            access_tokens=access_tokens,
            claude_api_key=claude_api_key,
            environment=environment,
            cert_path=project_root / cert_path_str,
            key_path=project_root / key_path_str,
            database_path=project_root / database_path_str,
        )
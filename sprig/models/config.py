"""Configuration loading for Sprig."""

from pathlib import Path
from typing import List

from pydantic import BaseModel, Field, field_validator

from sprig import credentials


class TellerAccessToken(BaseModel):
    """Validated Teller access token."""
    token: str = Field(..., pattern=r'^token_[a-z0-9]{26}$', description="Teller access tokens start with 'token_' followed by exactly 26 lowercase alphanumeric characters")


class Config(BaseModel):
    """Configuration for Sprig (API keys, paths, certificates)."""

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
        """Load configuration from keyring."""
        project_root = Path(__file__).parent.parent.parent

        creds = {
            'app_id': credentials.KEY_APP_ID,
            'access_tokens_str': credentials.KEY_ACCESS_TOKENS,
            'claude_api_key': credentials.KEY_CLAUDE_API_KEY,
            'environment': credentials.KEY_ENVIRONMENT,
            'cert_path_str': credentials.KEY_CERT_PATH,
            'key_path_str': credentials.KEY_KEY_PATH,
            'database_path_str': credentials.KEY_DATABASE_PATH,
        }

        values = {name: credentials.get_credential(key) for name, key in creds.items()}

        access_tokens = []
        if values['access_tokens_str']:
            access_tokens = [TellerAccessToken(token=token) for token in values['access_tokens_str'].split(",") if token]

        return cls(
            app_id=values['app_id'],
            access_tokens=access_tokens,
            claude_api_key=values['claude_api_key'],
            environment=values['environment'] or "development",
            cert_path=project_root / values['cert_path_str'],
            key_path=project_root / values['key_path_str'],
            database_path=project_root / (values['database_path_str'] or "sprig.db"),
        )
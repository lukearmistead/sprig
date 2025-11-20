"""Credential management using system keyring."""

from pathlib import Path
from typing import Optional, List
import keyring

from sprig.models.credentials import (
    TellerAppId,
    ClaudeAPIKey,
    CertPath,
    KeyPath,
    DatabasePath,
    Environment,
)
from sprig.models.teller import TellerAccessToken


class Credentials:
    """Manages credentials in system keyring."""

    SERVICE_NAME = "sprig"

    KEY_APP_ID = "app_id"
    KEY_ACCESS_TOKENS = "access_tokens"
    KEY_CLAUDE_API_KEY = "claude_api_key"
    KEY_CERT_PATH = "cert_path"
    KEY_KEY_PATH = "key_path"
    KEY_DATABASE_PATH = "database_path"
    KEY_ENVIRONMENT = "environment"

    def get(self, key: str) -> Optional[str]:
        """Get a credential from keyring."""
        return keyring.get_password(self.SERVICE_NAME, key)

    def set(self, key: str, value: str) -> bool:
        """Set a credential in keyring."""
        try:
            keyring.set_password(self.SERVICE_NAME, key, value)
            return True
        except Exception as e:
            print(f"Error setting credential '{key}': {e}")
            return False

    def append_token(self, new_token: str) -> bool:
        """Add a new access token to stored tokens."""
        existing_tokens_str = self.get(self.KEY_ACCESS_TOKENS)

        if existing_tokens_str:
            current_tokens = [token.strip() for token in existing_tokens_str.split(",") if token.strip()]
        else:
            current_tokens = []

        if new_token not in current_tokens:
            current_tokens.append(new_token)

        updated_token_string = ",".join(current_tokens)
        return self.set(self.KEY_ACCESS_TOKENS, updated_token_string)

    def mask(self, value: Optional[str], show_chars: int = 4) -> str:
        """Mask a credential value for display."""
        if value is None:
            return "<not set>"

        if len(value) <= show_chars:
            return "*" * len(value)

        return "*" * (len(value) - show_chars) + value[-show_chars:]

    def get_app_id(self) -> Optional[TellerAppId]:
        """Get validated Teller APP_ID."""
        raw = self.get(self.KEY_APP_ID)
        return TellerAppId(value=raw) if raw else None

    def get_claude_api_key(self) -> Optional[ClaudeAPIKey]:
        """Get validated Claude API key."""
        raw = self.get(self.KEY_CLAUDE_API_KEY)
        return ClaudeAPIKey(value=raw) if raw else None

    def get_access_tokens(self) -> List[TellerAccessToken]:
        """Get validated access tokens."""
        raw = self.get(self.KEY_ACCESS_TOKENS)
        if not raw:
            return []
        return [TellerAccessToken(token=t) for t in raw.split(",") if t]

    def get_cert_path(self) -> Optional[CertPath]:
        """Get validated certificate path."""
        raw = self.get(self.KEY_CERT_PATH)
        return CertPath(value=Path(raw)) if raw else None

    def get_key_path(self) -> Optional[KeyPath]:
        """Get validated private key path."""
        raw = self.get(self.KEY_KEY_PATH)
        return KeyPath(value=Path(raw)) if raw else None

    def get_database_path(self) -> Optional[DatabasePath]:
        """Get validated database path."""
        raw = self.get(self.KEY_DATABASE_PATH)
        return DatabasePath(value=Path(raw)) if raw else None

    def get_environment(self) -> Environment:
        """Get validated environment setting."""
        raw = self.get(self.KEY_ENVIRONMENT)
        return Environment(value=raw if raw else "development")


# Module-level singleton
_instance = Credentials()

# Expose instance methods at module level
get = _instance.get
set = _instance.set
append_token = _instance.append_token
mask = _instance.mask
get_app_id = _instance.get_app_id
get_claude_api_key = _instance.get_claude_api_key
get_access_tokens = _instance.get_access_tokens
get_cert_path = _instance.get_cert_path
get_key_path = _instance.get_key_path
get_database_path = _instance.get_database_path
get_environment = _instance.get_environment

# Expose keys at module level
KEY_APP_ID = Credentials.KEY_APP_ID
KEY_ACCESS_TOKENS = Credentials.KEY_ACCESS_TOKENS
KEY_CLAUDE_API_KEY = Credentials.KEY_CLAUDE_API_KEY
KEY_CERT_PATH = Credentials.KEY_CERT_PATH
KEY_KEY_PATH = Credentials.KEY_KEY_PATH
KEY_DATABASE_PATH = Credentials.KEY_DATABASE_PATH
KEY_ENVIRONMENT = Credentials.KEY_ENVIRONMENT

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


# Keyring service name
SERVICE_NAME = "sprig"

# Credential keys
KEY_APP_ID = "app_id"
KEY_ACCESS_TOKENS = "access_tokens"
KEY_CLAUDE_API_KEY = "claude_api_key"
KEY_CERT_PATH = "cert_path"
KEY_KEY_PATH = "key_path"
KEY_DATABASE_PATH = "database_path"
KEY_ENVIRONMENT = "environment"


def get(key: str) -> Optional[str]:
    """Get a credential from keyring."""
    return keyring.get_password(SERVICE_NAME, key)


def set(key: str, value: str) -> bool:
    """Set a credential in keyring."""
    try:
        keyring.set_password(SERVICE_NAME, key, value)
        return True
    except Exception as e:
        print(f"Error setting credential '{key}': {e}")
        return False


def append_token(new_token: str) -> bool:
    """Add a new access token to stored tokens."""
    existing_tokens_str = get(KEY_ACCESS_TOKENS)

    if existing_tokens_str:
        current_tokens = [token.strip() for token in existing_tokens_str.split(",") if token.strip()]
    else:
        current_tokens = []

    if new_token not in current_tokens:
        current_tokens.append(new_token)

    updated_token_string = ",".join(current_tokens)
    return set(KEY_ACCESS_TOKENS, updated_token_string)


def mask(value: Optional[str], show_chars: int = 4) -> str:
    """Mask a credential value for display."""
    if value is None:
        return "<not set>"

    if len(value) <= show_chars:
        return "*" * len(value)

    return "*" * (len(value) - show_chars) + value[-show_chars:]


def get_app_id() -> Optional[TellerAppId]:
    """Get validated Teller APP_ID."""
    raw = get(KEY_APP_ID)
    return TellerAppId(value=raw) if raw else None


def get_claude_api_key() -> Optional[ClaudeAPIKey]:
    """Get validated Claude API key."""
    raw = get(KEY_CLAUDE_API_KEY)
    return ClaudeAPIKey(value=raw) if raw else None


def get_access_tokens() -> List[TellerAccessToken]:
    """Get validated access tokens."""
    raw = get(KEY_ACCESS_TOKENS)
    if not raw:
        return []
    return [TellerAccessToken(token=t) for t in raw.split(",") if t]


def get_cert_path() -> Optional[CertPath]:
    """Get validated certificate path."""
    raw = get(KEY_CERT_PATH)
    if not raw:
        return None
    # Resolve relative to project root
    project_root = Path(__file__).parent.parent
    full_path = project_root / raw
    return CertPath(value=full_path)


def get_key_path() -> Optional[KeyPath]:
    """Get validated private key path."""
    raw = get(KEY_KEY_PATH)
    if not raw:
        return None
    # Resolve relative to project root
    project_root = Path(__file__).parent.parent
    full_path = project_root / raw
    return KeyPath(value=full_path)


def get_database_path() -> Optional[DatabasePath]:
    """Get validated database path."""
    raw = get(KEY_DATABASE_PATH)
    return DatabasePath(value=Path(raw)) if raw else None


def get_environment() -> Environment:
    """Get validated environment setting."""
    raw = get(KEY_ENVIRONMENT)
    return Environment(value=raw if raw else "development")

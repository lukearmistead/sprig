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
from pydantic import ValidationError
from sprig.models.teller import TellerAccessToken


# Keyring service name
SERVICE_NAME = "sprig"

# Credential configuration: key names and their validation models
CREDENTIALS = {
    "app_id": TellerAppId,
    "access_tokens": None,  # No validation model (comma-separated tokens)
    "claude_api_key": ClaudeAPIKey,
    "cert_path": CertPath,
    "key_path": KeyPath,
    "database_path": None,  # No validation model (may not exist yet)
    "environment": Environment,
}

# Backward compatibility constants
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


def store_credential(key: str, value: str) -> bool:
    """Store a credential in keyring with validation."""
    if not value:
        return True  # Allow empty values
        
    # Validate using Pydantic model if available
    model_class = CREDENTIALS.get(key)
    if model_class:
        model_class(value=value)  # Let Pydantic ValidationError propagate
    
    keyring.set_password(SERVICE_NAME, key, value)
    return True


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
    return store_credential(KEY_ACCESS_TOKENS, updated_token_string)


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
    return DatabasePath(value=raw) if raw else None


def get_environment() -> Environment:
    """Get validated environment setting."""
    raw = get(KEY_ENVIRONMENT)
    return Environment(value=raw if raw else "development")


def set_app_id(app_id: str) -> bool:
    """Set Teller APP_ID with validation."""
    return store_credential(KEY_APP_ID, app_id)


def set_claude_api_key(api_key: str) -> bool:
    """Set Claude API key with validation."""
    return store_credential(KEY_CLAUDE_API_KEY, api_key)


def set_cert_path(path: str) -> bool:
    """Set certificate path with validation."""
    return store_credential(KEY_CERT_PATH, path)


def set_key_path(path: str) -> bool:
    """Set private key path with validation."""
    return store_credential(KEY_KEY_PATH, path)


def set_environment(env: str) -> bool:
    """Set environment with validation."""
    return store_credential(KEY_ENVIRONMENT, env)


def set_database_path(path: str) -> bool:
    """Set database path."""
    return store_credential(KEY_DATABASE_PATH, path)

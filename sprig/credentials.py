"""Credential management using system keyring."""

import keyring
from typing import Optional

SERVICE_NAME = "sprig"

KEY_APP_ID = "app_id"
KEY_ACCESS_TOKENS = "access_tokens"
KEY_CLAUDE_API_KEY = "claude_api_key"
KEY_CERT_PATH = "cert_path"
KEY_KEY_PATH = "key_path"
KEY_DATABASE_PATH = "database_path"
KEY_ENVIRONMENT = "environment"


def get_credential(key: str) -> Optional[str]:
    """Get a credential from keyring."""
    return keyring.get_password(SERVICE_NAME, key)


def set_credential(key: str, value: str) -> bool:
    """Set a credential in keyring."""
    try:
        keyring.set_password(SERVICE_NAME, key, value)
        return True
    except Exception as e:
        print(f"Error setting credential '{key}': {e}")
        return False


def append_access_token(new_token: str) -> bool:
    """Add a new access token to stored tokens."""
    existing_tokens_str = get_credential(KEY_ACCESS_TOKENS)

    if existing_tokens_str:
        current_tokens = [token.strip() for token in existing_tokens_str.split(",") if token.strip()]
    else:
        current_tokens = []

    if new_token not in current_tokens:
        current_tokens.append(new_token)

    updated_token_string = ",".join(current_tokens)
    return set_credential(KEY_ACCESS_TOKENS, updated_token_string)


def mask_credential(value: Optional[str], show_chars: int = 4) -> str:
    """Mask a credential value for display."""
    if value is None:
        return "<not set>"

    if len(value) <= show_chars:
        return "*" * len(value)

    return "*" * (len(value) - show_chars) + value[-show_chars:]

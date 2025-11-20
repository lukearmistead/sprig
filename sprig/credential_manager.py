"""
Credential management using system keyring.

This module provides secure credential storage using the operating system's
keyring service (e.g., Keychain on macOS, Secret Service on Linux,
Credential Locker on Windows).

Falls back to .env file for backward compatibility.
"""

import os
from pathlib import Path
from typing import Optional, Dict, List
import keyring
from dotenv import load_dotenv, set_key

# Service name for keyring
SERVICE_NAME = "sprig"

# Credential keys
KEY_APP_ID = "app_id"
KEY_ACCESS_TOKENS = "access_tokens"
KEY_CLAUDE_API_KEY = "claude_api_key"
KEY_CERT_PATH = "cert_path"
KEY_KEY_PATH = "key_path"
KEY_DATABASE_PATH = "database_path"
KEY_ENVIRONMENT = "environment"


def get_credential(key: str, fallback_to_env: bool = True) -> Optional[str]:
    """
    Get a credential from keyring, with optional fallback to .env.

    Args:
        key: The credential key to retrieve
        fallback_to_env: If True, falls back to .env file if not found in keyring

    Returns:
        The credential value, or None if not found
    """
    # Try keyring first
    value = keyring.get_password(SERVICE_NAME, key)

    if value is not None:
        return value

    # Fall back to .env if requested
    if fallback_to_env:
        return os.getenv(key.upper())

    return None


def set_credential(key: str, value: str) -> bool:
    """
    Set a credential in the system keyring.

    Args:
        key: The credential key to set
        value: The credential value

    Returns:
        True if successful, False otherwise
    """
    try:
        keyring.set_password(SERVICE_NAME, key, value)
        return True
    except Exception as e:
        print(f"Error setting credential '{key}': {e}")
        return False


def delete_credential(key: str) -> bool:
    """
    Delete a credential from the system keyring.

    Args:
        key: The credential key to delete

    Returns:
        True if successful, False otherwise
    """
    try:
        keyring.delete_password(SERVICE_NAME, key)
        return True
    except Exception as e:
        # Check if it's a PasswordDeleteError (credential doesn't exist)
        if "PasswordDeleteError" in str(type(e)):
            return True
        print(f"Error deleting credential '{key}': {e}")
        return False


def get_all_credentials(fallback_to_env: bool = True) -> Dict[str, Optional[str]]:
    """
    Get all Sprig credentials.

    Args:
        fallback_to_env: If True, falls back to .env file for missing credentials

    Returns:
        Dictionary of all credentials
    """
    keys = [
        KEY_APP_ID,
        KEY_ACCESS_TOKENS,
        KEY_CLAUDE_API_KEY,
        KEY_CERT_PATH,
        KEY_KEY_PATH,
        KEY_DATABASE_PATH,
        KEY_ENVIRONMENT,
    ]

    return {key: get_credential(key, fallback_to_env) for key in keys}


def has_keyring_credentials() -> bool:
    """
    Check if any credentials are stored in keyring.

    Returns:
        True if at least one credential is in keyring
    """
    required_keys = [KEY_APP_ID, KEY_ACCESS_TOKENS, KEY_CLAUDE_API_KEY]
    return any(keyring.get_password(SERVICE_NAME, key) is not None for key in required_keys)


def migrate_from_env() -> Dict[str, bool]:
    """
    Migrate credentials from .env file to keyring.

    Returns:
        Dictionary mapping credential keys to migration success status
    """
    # Load .env file
    project_root = Path(__file__).parent.parent
    load_dotenv(project_root / ".env")

    results = {}

    # Migrate each credential
    credentials = {
        KEY_APP_ID: os.getenv("APP_ID"),
        KEY_ACCESS_TOKENS: os.getenv("ACCESS_TOKENS"),
        KEY_CLAUDE_API_KEY: os.getenv("CLAUDE_API_KEY"),
        KEY_CERT_PATH: os.getenv("CERT_PATH"),
        KEY_KEY_PATH: os.getenv("KEY_PATH"),
        KEY_DATABASE_PATH: os.getenv("DATABASE_PATH"),
        KEY_ENVIRONMENT: os.getenv("ENVIRONMENT"),
    }

    for key, value in credentials.items():
        if value:
            results[key] = set_credential(key, value)
        else:
            results[key] = False

    return results


def clear_all_credentials() -> Dict[str, bool]:
    """
    Clear all credentials from keyring.

    Returns:
        Dictionary mapping credential keys to deletion success status
    """
    keys = [
        KEY_APP_ID,
        KEY_ACCESS_TOKENS,
        KEY_CLAUDE_API_KEY,
        KEY_CERT_PATH,
        KEY_KEY_PATH,
        KEY_DATABASE_PATH,
        KEY_ENVIRONMENT,
    ]

    return {key: delete_credential(key) for key in keys}


def append_access_token(new_token: str) -> bool:
    """
    Add a new access token to the stored tokens.

    This function retrieves existing tokens, adds the new one if not already present,
    and stores the updated list.

    Args:
        new_token: The new access token to add

    Returns:
        True if successful, False otherwise
    """
    # Get existing tokens
    existing_tokens_str = get_credential(KEY_ACCESS_TOKENS, fallback_to_env=True)

    if existing_tokens_str:
        current_tokens = [token.strip() for token in existing_tokens_str.split(",") if token.strip()]
    else:
        current_tokens = []

    # Add new token if not already present
    if new_token not in current_tokens:
        current_tokens.append(new_token)

    # Store updated tokens in keyring
    updated_token_string = ",".join(current_tokens)
    return set_credential(KEY_ACCESS_TOKENS, updated_token_string)


def mask_credential(value: Optional[str], show_chars: int = 4) -> str:
    """
    Mask a credential value for display purposes.

    Args:
        value: The credential value to mask
        show_chars: Number of characters to show at the end

    Returns:
        Masked credential string
    """
    if value is None:
        return "<not set>"

    if len(value) <= show_chars:
        return "*" * len(value)

    return "*" * (len(value) - show_chars) + value[-show_chars:]

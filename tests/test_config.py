"""Tests for sprig.config module."""

import os
from pathlib import Path
from unittest.mock import patch, MagicMock

from sprig.models import Config
from sprig import credentials


@patch('sprig.models.config.credentials.get_credential')
def test_config_load(mock_get_credential):
    """Test that Config.load() works correctly with mocked credentials."""
    # Mock credential responses
    project_root = Path(__file__).parent.parent
    cert_path = project_root / "certs" / "certificate.pem"
    key_path = project_root / "certs" / "private_key.pem"

    # Create mock cert files if they don't exist (for testing)
    cert_path.parent.mkdir(parents=True, exist_ok=True)
    if not cert_path.exists():
        cert_path.touch()
    if not key_path.exists():
        key_path.touch()

    def mock_get(key):
        mock_values = {
            credentials.KEY_APP_ID: "app_test12345678901234567",
            credentials.KEY_ACCESS_TOKENS: "token_abcdefghijklmnopqrstuvwxyz",
            credentials.KEY_CLAUDE_API_KEY: "sk-ant-api03-" + "a" * 95,
            credentials.KEY_ENVIRONMENT: "development",
            credentials.KEY_CERT_PATH: "certs/certificate.pem",
            credentials.KEY_KEY_PATH: "certs/private_key.pem",
            credentials.KEY_DATABASE_PATH: "sprig.db",
        }
        return mock_values.get(key)

    mock_get_credential.side_effect = mock_get

    config = Config.load()

    assert config.app_id == "app_test12345678901234567"
    assert len(config.access_tokens) > 0
    assert config.environment in ["sandbox", "development", "production"]
    assert config.cert_path.exists()
    assert config.key_path.exists()
    assert config.database_path.name == "sprig.db"
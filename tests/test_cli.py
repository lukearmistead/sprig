"""Tests for sprig CLI functionality."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from sprig.cli import main, open_config, run_sync


def test_main_opens_config_when_missing_app_id():
    """When app_id is missing, CLI should open the config file."""
    mock_config = MagicMock()
    mock_config.app_id = ""
    mock_config.claude_key = "sk-test"

    with patch("sprig.cli.Config.load", return_value=mock_config), \
         patch("sprig.cli.get_default_config_path", return_value=Path("/path/to/config.yml")), \
         patch("sprig.cli.open_config") as mock_open, \
         patch("builtins.print"):
        main()
        mock_open.assert_called_once_with("/path/to/config.yml")


def test_main_opens_config_when_missing_claude_key():
    """When claude_key is missing, CLI should open the config file."""
    mock_config = MagicMock()
    mock_config.app_id = "test-app"
    mock_config.claude_key = ""

    with patch("sprig.cli.Config.load", return_value=mock_config), \
         patch("sprig.cli.get_default_config_path", return_value=Path("/path/to/config.yml")), \
         patch("sprig.cli.open_config") as mock_open, \
         patch("builtins.print"):
        main()
        mock_open.assert_called_once_with("/path/to/config.yml")


def test_main_runs_connect_when_no_accounts():
    """When credentials exist but no accounts, CLI should run connect flow."""
    mock_config = MagicMock()
    mock_config.app_id = "test-app"
    mock_config.claude_key = "sk-test"
    mock_config.access_tokens = []

    # After connect, still no tokens
    with patch("sprig.cli.Config.load", return_value=mock_config), \
         patch("sprig.cli.authenticate") as mock_auth, \
         patch("builtins.print"):
        main()
        mock_auth.assert_called_once_with(mock_config)


def test_main_runs_sync_when_configured():
    """When fully configured, CLI should run sync and offer to add accounts."""
    mock_config = MagicMock()
    mock_config.app_id = "test-app"
    mock_config.claude_key = "sk-test"
    mock_config.access_tokens = ["token1"]
    mock_config.from_date = "2024-01-01"
    mock_config.cert_path = "cert.pem"
    mock_config.key_path = "key.pem"

    with patch("sprig.cli.Config.load", return_value=mock_config), \
         patch("sprig.cli.run_sync") as mock_sync, \
         patch("builtins.input", return_value="n"):
        main()
        mock_sync.assert_called_once_with(mock_config)


def test_main_adds_account_when_user_says_yes():
    """After sync, user can add another account."""
    mock_config = MagicMock()
    mock_config.app_id = "test-app"
    mock_config.claude_key = "sk-test"
    mock_config.access_tokens = ["token1"]

    with patch("sprig.cli.Config.load", return_value=mock_config), \
         patch("sprig.cli.run_sync"), \
         patch("sprig.cli.authenticate") as mock_auth, \
         patch("builtins.input", return_value="y"):
        main()
        mock_auth.assert_called_once_with(mock_config)

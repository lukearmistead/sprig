"""Tests for sprig CLI functionality."""

from pathlib import Path
from unittest.mock import MagicMock, call, patch

from sprig.cli import main, open_config, run_sync


def _make_config(app_id="test-app", claude_key="sk-test", access_tokens=None):
    cfg = MagicMock()
    cfg.app_id = app_id
    cfg.claude_key = claude_key
    cfg.access_tokens = access_tokens or []
    return cfg


def test_main_opens_config_when_missing_app_id():
    """Missing app_id: opens config+certs, waits for input, reloads, then continues."""
    missing = _make_config(app_id="")
    valid = _make_config(access_tokens=["tok"])

    with patch("sprig.cli.Config.load", side_effect=[missing, valid, valid]), \
         patch("sprig.cli.get_default_config_path", return_value=Path("/cfg")), \
         patch("sprig.cli.get_default_certs_dir", return_value=Path("/certs")), \
         patch("sprig.cli.open_config") as mock_open, \
         patch("sprig.cli.run_sync"), \
         patch("builtins.input", return_value="n"), \
         patch("builtins.print"):
        main()
        assert mock_open.call_count == 2
        mock_open.assert_any_call("/cfg")
        mock_open.assert_any_call("/certs")


def test_main_opens_config_when_missing_claude_key():
    """Missing claude_key: opens config+certs, waits, reloads, continues."""
    missing = _make_config(claude_key="")
    valid = _make_config(access_tokens=["tok"])

    with patch("sprig.cli.Config.load", side_effect=[missing, valid, valid]), \
         patch("sprig.cli.get_default_config_path", return_value=Path("/cfg")), \
         patch("sprig.cli.get_default_certs_dir", return_value=Path("/certs")), \
         patch("sprig.cli.open_config") as mock_open, \
         patch("sprig.cli.run_sync"), \
         patch("builtins.input", return_value="n"), \
         patch("builtins.print"):
        main()
        assert mock_open.call_count == 2
        mock_open.assert_any_call("/cfg")
        mock_open.assert_any_call("/certs")


def test_main_runs_connect_when_no_accounts():
    """Valid creds but no accounts: authenticates, reloads config, then syncs."""
    no_tokens = _make_config()
    with_tokens = _make_config(access_tokens=["tok"])

    with patch("sprig.cli.Config.load", side_effect=[no_tokens, with_tokens, with_tokens]), \
         patch("sprig.cli.authenticate") as mock_auth, \
         patch("sprig.cli.run_sync") as mock_sync, \
         patch("builtins.input", return_value="n"), \
         patch("builtins.print"):
        main()
        mock_auth.assert_called_once_with(no_tokens)
        mock_sync.assert_called_once_with(with_tokens)


def test_main_runs_sync_when_configured():
    """Fully configured: skips both loops, runs sync."""
    cfg = _make_config(access_tokens=["token1"])

    with patch("sprig.cli.Config.load", return_value=cfg), \
         patch("sprig.cli.run_sync") as mock_sync, \
         patch("builtins.input", return_value="n"):
        main()
        mock_sync.assert_called_once_with(cfg)


def test_main_adds_account_when_user_says_yes():
    """After sync, user can add another account."""
    cfg = _make_config(access_tokens=["token1"])

    with patch("sprig.cli.Config.load", return_value=cfg), \
         patch("sprig.cli.run_sync"), \
         patch("sprig.cli.authenticate") as mock_auth, \
         patch("builtins.input", return_value="y"):
        main()
        mock_auth.assert_called_once_with(cfg)


def test_main_full_first_run():
    """Full first-run: missing creds → fill in → no accounts → authenticate → sync."""
    missing_creds = _make_config(app_id="", claude_key="")
    valid_no_tokens = _make_config()
    valid_with_tokens = _make_config(access_tokens=["tok"])

    with patch("sprig.cli.Config.load", side_effect=[
            missing_creds, valid_no_tokens, valid_with_tokens, valid_with_tokens,
         ]), \
         patch("sprig.cli.get_default_config_path", return_value=Path("/cfg")), \
         patch("sprig.cli.get_default_certs_dir", return_value=Path("/certs")), \
         patch("sprig.cli.open_config") as mock_open, \
         patch("sprig.cli.authenticate") as mock_auth, \
         patch("sprig.cli.run_sync") as mock_sync, \
         patch("builtins.input", return_value="n"), \
         patch("builtins.print"):
        main()
        assert mock_open.call_count == 2
        mock_auth.assert_called_once_with(valid_no_tokens)
        mock_sync.assert_called_once_with(valid_with_tokens)

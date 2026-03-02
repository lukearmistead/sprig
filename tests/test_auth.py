"""Tests for authentication module."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from pydantic import ValidationError

from sprig.auth import authenticate, _save_access_tokens
from sprig.models.config import Config, load_config
from sprig.models.teller import TellerAccessToken


class TestTellerAccessToken:
    def test_valid_token(self):
        TellerAccessToken(token="token_3yxxieo64rfc57p4tux3an5v2a")
        TellerAccessToken(token="token_abcdefghijklmnopqrstuvwxyz")

    def test_invalid_format(self):
        with pytest.raises(ValidationError):
            TellerAccessToken(token="test_tkn_abc123")
        with pytest.raises(ValidationError):
            TellerAccessToken(token="invalid_token")
        with pytest.raises(ValidationError):
            TellerAccessToken(token="")
        with pytest.raises(ValidationError):
            TellerAccessToken(token="token_ABC123")


class TestSaveAccessTokens:
    def test_round_trip(self):
        """Tokens written by _save_access_tokens survive a config reload."""
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.yml"
            config_data = {
                "categories": [{"name": "general", "description": "general"}],
                "batch_size": 50,
                "access_tokens": [],
            }
            with open(config_path, "w") as f:
                yaml.dump(config_data, f)

            _save_access_tokens(["token_aaaaaaaaaaaaaaaaaaaaaaaa"], config_path)

            reloaded = load_config(config_path)
            assert reloaded.access_tokens == ["token_aaaaaaaaaaaaaaaaaaaaaaaa"]

    def test_preserves_other_fields(self):
        """Writing tokens does not clobber unrelated config fields."""
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.yml"
            config_data = {
                "categories": [{"name": "dining", "description": "Restaurants"}],
                "batch_size": 25,
                "teller_app_id": "app_test12345678901234567",
                "access_tokens": [],
            }
            with open(config_path, "w") as f:
                yaml.dump(config_data, f)

            _save_access_tokens(["token_bbbbbbbbbbbbbbbbbbbbbbbb"], config_path)

            reloaded = load_config(config_path)
            assert reloaded.teller_app_id == "app_test12345678901234567"
            assert reloaded.batch_size == 25
            assert reloaded.categories[0].name == "dining"


class TestAuthenticate:
    def _make_config(self, **overrides):
        defaults = {
            "categories": [{"name": "general", "description": "general"}],
            "batch_size": 50,
            "teller_app_id": "app_test12345678901234567",
        }
        defaults.update(overrides)
        return Config(**defaults)

    def test_authenticate_success(self):
        config = self._make_config()
        with patch('sprig.auth.run_auth_server') as mock_run:
            mock_run.return_value = "1"
            assert authenticate(config) is True
            mock_run.assert_called_once_with(config, 8001)

    def test_authenticate_multiple_accounts(self):
        config = self._make_config()
        with patch('sprig.auth.run_auth_server') as mock_run:
            mock_run.return_value = "3"
            assert authenticate(config) is True

    def test_authenticate_cancelled(self):
        config = self._make_config()
        with patch('sprig.auth.run_auth_server') as mock_run:
            mock_run.return_value = None
            assert authenticate(config) is False

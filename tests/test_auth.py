"""Tests for authentication module."""

from unittest.mock import patch

import pytest
from pydantic import ValidationError

from sprig.auth import authenticate
from sprig.models.config import Config
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


class TestAuthenticate:
    def _make_config(self, **overrides):
        defaults = {
            "categories": [{"name": "general", "description": "general"}],
            "batch_size": 50,
            "app_id": "app_test12345678901234567",
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

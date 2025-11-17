"""Tests for authentication module."""

from unittest.mock import patch

import pytest

from sprig.auth import append_token_to_env, authenticate
from sprig.models.runtime_config import TellerAccessToken
from pydantic import ValidationError


class TestTellerAccessToken:
    """Test Teller access token validation."""

    def test_valid_token(self):
        """Should accept valid tokens."""
        TellerAccessToken(token="token_3yxxieo64rfc57p4tux3an5v2a")
        TellerAccessToken(token="token_abc123def456")

    def test_invalid_format(self):
        """Should reject tokens with invalid format."""
        with pytest.raises(ValidationError):
            TellerAccessToken(token="test_tkn_abc123")

        with pytest.raises(ValidationError):
            TellerAccessToken(token="invalid_token")

        with pytest.raises(ValidationError):
            TellerAccessToken(token="")

        with pytest.raises(ValidationError):
            TellerAccessToken(token="token_ABC123")  # uppercase not allowed


class TestAppendTokenToEnv:
    """Test .env file token updates."""

    def test_missing_env_file(self):
        """Should return False if .env file doesn't exist."""
        with patch('sprig.auth.Path') as mock_path:
            mock_env_path = mock_path.return_value.parent.parent.__truediv__.return_value
            mock_env_path.exists.return_value = False

            result = append_token_to_env("token_abc123")
            assert result is False


class TestAuthenticate:
    """Test the authenticate function with UI-based multi-account support."""

    def test_authenticate_success(self):
        """Should successfully authenticate when server returns account count."""
        with patch('sprig.auth.os.getenv') as mock_getenv, \
             patch('sprig.auth.run_auth_server') as mock_run_auth:

            mock_getenv.return_value = "test_app_id"
            mock_run_auth.return_value = "1"  # One account added

            result = authenticate("development", 8001)

            assert result is True
            mock_run_auth.assert_called_once_with("test_app_id", "development", 8001)

    def test_authenticate_multiple_accounts_via_ui(self):
        """Should handle multiple accounts added via UI."""
        with patch('sprig.auth.os.getenv') as mock_getenv, \
             patch('sprig.auth.run_auth_server') as mock_run_auth:

            mock_getenv.return_value = "test_app_id"
            mock_run_auth.return_value = "3"  # Three accounts added via UI

            result = authenticate("development", 8001)

            assert result is True
            mock_run_auth.assert_called_once()

    def test_authenticate_missing_app_id(self):
        """Should return False if APP_ID is not set."""
        with patch('sprig.auth.os.getenv') as mock_getenv:
            mock_getenv.return_value = None

            result = authenticate("development", 8001)

            assert result is False

    def test_authenticate_cancelled(self):
        """Should return False if authentication is cancelled."""
        with patch('sprig.auth.os.getenv') as mock_getenv, \
             patch('sprig.auth.run_auth_server') as mock_run_auth:

            mock_getenv.return_value = "test_app_id"
            mock_run_auth.return_value = None  # No accounts added

            result = authenticate("development", 8001)

            assert result is False
            mock_run_auth.assert_called_once()

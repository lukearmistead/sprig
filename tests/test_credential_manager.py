"""Tests for credential manager module."""

from unittest.mock import Mock, patch
import pytest

from sprig import credential_manager


class TestGetCredential:
    """Test get_credential function."""

    @patch('sprig.credential_manager.keyring')
    def test_get_from_keyring(self, mock_keyring):
        """Should return credential from keyring."""
        mock_keyring.get_password.return_value = "keyring_value"

        result = credential_manager.get_credential("test_key")

        assert result == "keyring_value"
        mock_keyring.get_password.assert_called_once_with("sprig", "test_key")

    @patch('sprig.credential_manager.keyring')
    def test_get_returns_none_when_missing(self, mock_keyring):
        """Should return None when credential not in keyring."""
        mock_keyring.get_password.return_value = None

        result = credential_manager.get_credential("test_key")

        assert result is None


class TestSetCredential:
    """Test set_credential function."""

    @patch('sprig.credential_manager.keyring')
    def test_set_credential_success(self, mock_keyring):
        """Should successfully set credential in keyring."""
        result = credential_manager.set_credential("test_key", "test_value")

        assert result is True
        mock_keyring.set_password.assert_called_once_with("sprig", "test_key", "test_value")

    @patch('sprig.credential_manager.keyring')
    def test_set_credential_failure(self, mock_keyring):
        """Should return False when setting credential fails."""
        mock_keyring.set_password.side_effect = Exception("Keyring error")

        result = credential_manager.set_credential("test_key", "test_value")

        assert result is False


class TestAppendAccessToken:
    """Test append_access_token function."""

    @patch('sprig.credential_manager.get_credential')
    @patch('sprig.credential_manager.set_credential')
    def test_append_new_token(self, mock_set_credential, mock_get_credential):
        """Should append new token to existing tokens."""
        mock_get_credential.return_value = "token_existing123456789012345678"
        mock_set_credential.return_value = True

        result = credential_manager.append_access_token("token_new456789012345678901234")

        assert result is True
        call_args = mock_set_credential.call_args[0]
        assert call_args[0] == credential_manager.KEY_ACCESS_TOKENS
        assert "token_existing123456789012345678" in call_args[1]
        assert "token_new456789012345678901234" in call_args[1]

    @patch('sprig.credential_manager.get_credential')
    @patch('sprig.credential_manager.set_credential')
    def test_append_duplicate_token(self, mock_set_credential, mock_get_credential):
        """Should not duplicate existing token."""
        mock_get_credential.return_value = "token_existing123456789012345678,token_test456789012345678901234"
        mock_set_credential.return_value = True

        result = credential_manager.append_access_token("token_test456789012345678901234")

        assert result is True
        call_args = mock_set_credential.call_args[0]
        tokens = call_args[1].split(",")
        assert len(tokens) == 2

    @patch('sprig.credential_manager.get_credential')
    @patch('sprig.credential_manager.set_credential')
    def test_append_token_when_none_exist(self, mock_set_credential, mock_get_credential):
        """Should handle case when no tokens exist."""
        mock_get_credential.return_value = None
        mock_set_credential.return_value = True

        result = credential_manager.append_access_token("token_new456789012345678901234")

        assert result is True
        call_args = mock_set_credential.call_args[0]
        assert call_args[1] == "token_new456789012345678901234"


class TestMaskCredential:
    """Test mask_credential function."""

    def test_mask_long_credential(self):
        """Should mask long credentials showing last 4 characters."""
        result = credential_manager.mask_credential("app_1234567890abcdefghijk")

        assert result == "*********************hijk"
        assert len(result) == 25

    def test_mask_short_credential(self):
        """Should mask entire short credential."""
        result = credential_manager.mask_credential("abc")

        assert result == "***"

    def test_mask_none_credential(self):
        """Should return '<not set>' for None."""
        result = credential_manager.mask_credential(None)

        assert result == "<not set>"

    def test_mask_credential_custom_show_chars(self):
        """Should respect custom show_chars parameter."""
        result = credential_manager.mask_credential("1234567890", show_chars=2)

        assert result == "********90"

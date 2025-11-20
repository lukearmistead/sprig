"""Tests for credential manager module."""

import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

from sprig import credential_manager


class TestGetCredential:
    """Test get_credential function."""

    @patch('sprig.credential_manager.keyring')
    def test_get_from_keyring_when_available(self, mock_keyring):
        """Should return credential from keyring when available."""
        mock_keyring.get_password.return_value = "keyring_value"

        result = credential_manager.get_credential("test_key")

        assert result == "keyring_value"
        mock_keyring.get_password.assert_called_once_with("sprig", "test_key")

    @patch('sprig.credential_manager.keyring')
    @patch.dict(os.environ, {'TEST_KEY': 'env_value'})
    def test_fallback_to_env_when_not_in_keyring(self, mock_keyring):
        """Should fallback to environment variable when not in keyring."""
        mock_keyring.get_password.return_value = None

        result = credential_manager.get_credential("test_key", fallback_to_env=True)

        assert result == "env_value"

    @patch('sprig.credential_manager.keyring')
    def test_no_fallback_when_disabled(self, mock_keyring):
        """Should return None when fallback is disabled and not in keyring."""
        mock_keyring.get_password.return_value = None

        result = credential_manager.get_credential("test_key", fallback_to_env=False)

        assert result is None

    @patch('sprig.credential_manager.keyring')
    def test_prefer_keyring_over_env(self, mock_keyring):
        """Should prefer keyring value over environment variable."""
        mock_keyring.get_password.return_value = "keyring_value"

        with patch.dict(os.environ, {'TEST_KEY': 'env_value'}):
            result = credential_manager.get_credential("test_key", fallback_to_env=True)

        assert result == "keyring_value"


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


class TestDeleteCredential:
    """Test delete_credential function."""

    @patch('sprig.credential_manager.keyring')
    def test_delete_credential_success(self, mock_keyring):
        """Should successfully delete credential from keyring."""
        result = credential_manager.delete_credential("test_key")

        assert result is True
        mock_keyring.delete_password.assert_called_once_with("sprig", "test_key")

    @patch('sprig.credential_manager.keyring')
    def test_delete_nonexistent_credential(self, mock_keyring):
        """Should return True when credential doesn't exist."""
        mock_keyring.errors.PasswordDeleteError = type('PasswordDeleteError', (Exception,), {})
        mock_keyring.delete_password.side_effect = mock_keyring.errors.PasswordDeleteError()

        result = credential_manager.delete_credential("test_key")

        assert result is True

    @patch('sprig.credential_manager.keyring')
    def test_delete_credential_error(self, mock_keyring):
        """Should return False when deletion fails with unexpected error."""
        mock_keyring.delete_password.side_effect = Exception("Unexpected error")

        result = credential_manager.delete_credential("test_key")

        assert result is False


class TestGetAllCredentials:
    """Test get_all_credentials function."""

    @patch('sprig.credential_manager.get_credential')
    def test_get_all_credentials(self, mock_get_credential):
        """Should retrieve all credential keys."""
        mock_get_credential.return_value = "test_value"

        result = credential_manager.get_all_credentials()

        assert len(result) == 7  # Should have 7 credential keys
        assert credential_manager.KEY_APP_ID in result
        assert credential_manager.KEY_ACCESS_TOKENS in result
        assert credential_manager.KEY_CLAUDE_API_KEY in result


class TestHasKeyringCredentials:
    """Test has_keyring_credentials function."""

    @patch('sprig.credential_manager.keyring')
    def test_has_keyring_credentials_when_present(self, mock_keyring):
        """Should return True when at least one credential is in keyring."""
        mock_keyring.get_password.side_effect = lambda service, key: "value" if key == "app_id" else None

        result = credential_manager.has_keyring_credentials()

        assert result is True

    @patch('sprig.credential_manager.keyring')
    def test_has_no_keyring_credentials(self, mock_keyring):
        """Should return False when no credentials are in keyring."""
        mock_keyring.get_password.return_value = None

        result = credential_manager.has_keyring_credentials()

        assert result is False


class TestMigrateFromEnv:
    """Test migrate_from_env function."""

    @patch('sprig.credential_manager.load_dotenv')
    @patch('sprig.credential_manager.set_credential')
    def test_migrate_from_env_success(self, mock_set_credential, mock_load_dotenv):
        """Should migrate credentials from .env to keyring."""
        mock_set_credential.return_value = True

        with patch.dict(os.environ, {
            'APP_ID': 'app_test123',
            'ACCESS_TOKENS': 'token_test456',
            'CLAUDE_API_KEY': 'sk-ant-test',
        }):
            results = credential_manager.migrate_from_env()

        assert results[credential_manager.KEY_APP_ID] is True
        assert results[credential_manager.KEY_ACCESS_TOKENS] is True
        assert results[credential_manager.KEY_CLAUDE_API_KEY] is True

    @patch('sprig.credential_manager.load_dotenv')
    @patch('sprig.credential_manager.set_credential')
    def test_migrate_from_env_partial_failure(self, mock_set_credential, mock_load_dotenv):
        """Should handle partial migration failures."""
        mock_set_credential.side_effect = [True, False, True, False, False, False, False]

        with patch.dict(os.environ, {
            'APP_ID': 'app_test123',
            'ACCESS_TOKENS': 'token_test456',
            'CLAUDE_API_KEY': 'sk-ant-test',
        }):
            results = credential_manager.migrate_from_env()

        assert results[credential_manager.KEY_APP_ID] is True
        assert results[credential_manager.KEY_ACCESS_TOKENS] is False


class TestClearAllCredentials:
    """Test clear_all_credentials function."""

    @patch('sprig.credential_manager.delete_credential')
    def test_clear_all_credentials(self, mock_delete_credential):
        """Should clear all credentials from keyring."""
        mock_delete_credential.return_value = True

        results = credential_manager.clear_all_credentials()

        assert len(results) == 7  # Should clear 7 credential keys
        assert all(v is True for v in results.values())


class TestAppendAccessToken:
    """Test append_access_token function."""

    @patch('sprig.credential_manager.get_credential')
    @patch('sprig.credential_manager.set_credential')
    def test_append_new_token(self, mock_set_credential, mock_get_credential):
        """Should append new token to existing tokens."""
        mock_get_credential.return_value = "token_existing123"
        mock_set_credential.return_value = True

        result = credential_manager.append_access_token("token_new456")

        assert result is True
        # Should be called with both tokens
        call_args = mock_set_credential.call_args[0]
        assert call_args[0] == credential_manager.KEY_ACCESS_TOKENS
        assert "token_existing123" in call_args[1]
        assert "token_new456" in call_args[1]

    @patch('sprig.credential_manager.get_credential')
    @patch('sprig.credential_manager.set_credential')
    def test_append_duplicate_token(self, mock_set_credential, mock_get_credential):
        """Should not duplicate existing token."""
        mock_get_credential.return_value = "token_existing123,token_test456"
        mock_set_credential.return_value = True

        result = credential_manager.append_access_token("token_test456")

        assert result is True
        # Should still only have 2 tokens
        call_args = mock_set_credential.call_args[0]
        tokens = call_args[1].split(",")
        assert len(tokens) == 2

    @patch('sprig.credential_manager.get_credential')
    @patch('sprig.credential_manager.set_credential')
    def test_append_token_when_none_exist(self, mock_set_credential, mock_get_credential):
        """Should handle case when no tokens exist."""
        mock_get_credential.return_value = None
        mock_set_credential.return_value = True

        result = credential_manager.append_access_token("token_new456")

        assert result is True
        call_args = mock_set_credential.call_args[0]
        assert call_args[1] == "token_new456"


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

"""Tests for authentication module."""

from unittest.mock import patch

import pytest

from sprig.auth import append_token_to_env
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
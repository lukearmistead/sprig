"""Tests for sprig.teller_client module."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from sprig.models import RuntimeConfig
from sprig.teller_client import TellerClient


def create_test_config():
    """Create a test config with temporary certificate files."""
    temp_dir = Path(tempfile.mkdtemp())
    
    # Create dummy certificate files
    cert_path = temp_dir / "cert.pem"
    key_path = temp_dir / "key.pem"
    cert_path.write_text("dummy cert content")
    key_path.write_text("dummy key content")
    
    config = RuntimeConfig(
        app_id="test_app_id",
        access_tokens=["test_token_1", "test_token_2"],
        claude_api_key="test_claude_key",
        environment="development",
        cert_path=cert_path,
        key_path=key_path,
        database_path=temp_dir / "test.db"
    )
    return config


def test_teller_client_initialization():
    """Test TellerClient initialization and certificate setup."""
    config = create_test_config()
    client = TellerClient(config)
    
    assert client.config == config
    assert client.base_url == "https://api.teller.io"
    assert client.session.cert == (str(config.cert_path), str(config.key_path))


@patch('requests.Session.get')
def test_make_request(mock_get):
    """Test _make_request method."""
    config = create_test_config()
    client = TellerClient(config)
    
    # Mock successful response
    mock_response = Mock()
    mock_response.json.return_value = {"test": "data"}
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response
    
    # Call _make_request
    result = client._make_request("test_token", "/test/endpoint")
    
    # Verify request was made correctly
    mock_get.assert_called_once_with(
        "https://api.teller.io/test/endpoint",
        auth=("test_token", ""),
        headers={"Content-Type": "application/json"}
    )
    
    # Verify response handling
    mock_response.raise_for_status.assert_called_once()
    mock_response.json.assert_called_once()
    assert result == {"test": "data"}


@patch('requests.Session.get')
def test_make_request_http_error(mock_get):
    """Test _make_request with HTTP error."""
    config = create_test_config()
    client = TellerClient(config)
    
    # Mock response that raises HTTP error
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
    mock_get.return_value = mock_response
    
    # Verify exception is raised
    try:
        client._make_request("test_token", "/bad/endpoint")
        assert False, "Expected HTTPError to be raised"
    except requests.HTTPError as e:
        assert "404 Not Found" in str(e)


@patch('sprig.teller_client.TellerClient._make_request')
def test_get_accounts(mock_make_request):
    """Test get_accounts method."""
    config = create_test_config()
    client = TellerClient(config)
    
    mock_accounts = [
        {
            "id": "acc_123",
            "name": "Test Account",
            "type": "depository",
            "currency": "USD",
            "status": "open"
        }
    ]
    mock_make_request.return_value = mock_accounts
    
    result = client.get_accounts("test_token")
    
    mock_make_request.assert_called_once_with("test_token", "/accounts")
    assert result == mock_accounts


@patch('sprig.teller_client.TellerClient._make_request')
def test_get_transactions(mock_make_request):
    """Test get_transactions method."""
    config = create_test_config()
    client = TellerClient(config)
    
    mock_transactions = [
        {
            "id": "txn_123",
            "account_id": "acc_456",
            "amount": 25.50,
            "description": "Test Transaction",
            "date": "2024-01-15",
            "type": "card_payment",
            "status": "posted"
        }
    ]
    mock_make_request.return_value = mock_transactions
    
    result = client.get_transactions("test_token", "acc_456")
    
    mock_make_request.assert_called_once_with("test_token", "/accounts/acc_456/transactions")
    assert result == mock_transactions


def test_client_without_certificates():
    """Test client initialization when certificate files don't exist."""
    # Create config with non-existent certificate paths
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        RuntimeConfig(
            app_id="test_app_id",
            access_tokens=["test_token"],
            environment="development", 
            cert_path=temp_dir / "nonexistent_cert.pem",
            key_path=temp_dir / "nonexistent_key.pem",
            database_path=temp_dir / "test.db"
        )
        assert False, "Expected ValueError for missing certificate files"
    except ValueError as e:
        assert "File does not exist" in str(e)


@patch('requests.Session.get')
def test_get_accounts_integration_style(mock_get):
    """Integration-style test with realistic API response."""
    config = create_test_config()
    client = TellerClient(config)
    
    # Mock realistic Teller API response
    mock_response = Mock()
    mock_response.json.return_value = [
        {
            "id": "acc_o9b5x8q7k6m2n4p1r3s5t7u9",
            "name": "Chase Sapphire Preferred",
            "type": "credit",
            "subtype": "credit_card", 
            "institution": {
                "name": "Chase",
                "id": "chase"
            },
            "currency": "USD",
            "status": "open",
            "last_four": "1234",
            "links": {
                "self": "https://api.teller.io/accounts/acc_o9b5x8q7k6m2n4p1r3s5t7u9",
                "transactions": "https://api.teller.io/accounts/acc_o9b5x8q7k6m2n4p1r3s5t7u9/transactions"
            }
        }
    ]
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response
    
    # Call get_accounts
    result = client.get_accounts("live_token_example")
    
    # Verify realistic request
    mock_get.assert_called_once_with(
        "https://api.teller.io/accounts",
        auth=("live_token_example", ""),
        headers={"Content-Type": "application/json"}
    )
    
    # Verify realistic response
    assert len(result) == 1
    assert result[0]["name"] == "Chase Sapphire Preferred"
    assert result[0]["type"] == "credit"
    assert result[0]["last_four"] == "1234"
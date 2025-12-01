"""Tests for sprig.teller_client module."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
import pytest

import requests

from sprig.teller_client import TellerClient
from sprig.models.credentials import CertPath, KeyPath


@pytest.fixture
def mock_certs():
    """Create temporary certificate files and mock credentials."""
    temp_dir = Path(tempfile.mkdtemp())

    # Create dummy certificate files
    cert_path = temp_dir / "cert.pem"
    key_path = temp_dir / "key.pem"
    cert_path.write_text("dummy cert content")
    key_path.write_text("dummy key content")

    with patch('sprig.teller_client.credentials.get_cert_path') as mock_cert, \
         patch('sprig.teller_client.credentials.get_key_path') as mock_key:
        mock_cert.return_value = CertPath(value=cert_path)
        mock_key.return_value = KeyPath(value=key_path)
        yield cert_path, key_path


def test_teller_client_initialization(mock_certs):
    """Test TellerClient initialization and certificate setup."""
    cert_path, key_path = mock_certs
    client = TellerClient()

    assert client.base_url == "https://api.teller.io"
    # Note: cert paths are resolved relative to project root, so we can't directly compare


@patch('requests.Session.get')
def test_make_request(mock_get, mock_certs):
    """Test _make_request method."""
    client = TellerClient()
    
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
def test_make_request_http_error(mock_get, mock_certs):
    """Test _make_request with HTTP error."""
    client = TellerClient()
    
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
def test_get_accounts(mock_make_request, mock_certs):
    """Test get_accounts method."""
    client = TellerClient()
    
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
def test_get_transactions(mock_make_request, mock_certs):
    """Test get_transactions method."""
    client = TellerClient()

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


@patch('sprig.teller_client.TellerClient._make_request')
def test_get_transactions_with_start_date(mock_make_request, mock_certs):
    """Test get_transactions method with start_date parameter."""
    from datetime import date

    client = TellerClient()

    mock_transactions = [
        {
            "id": "txn_123",
            "account_id": "acc_456",
            "amount": 25.50,
            "description": "Recent Transaction",
            "date": "2024-03-15",
            "type": "card_payment",
            "status": "posted"
        }
    ]
    mock_make_request.return_value = mock_transactions

    start_date = date(2024, 3, 1)
    result = client.get_transactions("test_token", "acc_456", start_date)

    mock_make_request.assert_called_once_with("test_token", "/accounts/acc_456/transactions?start_date=2024-03-01")
    assert result == mock_transactions


@patch('requests.Session.get')
def test_get_accounts_integration_style(mock_get, mock_certs):
    """Integration-style test with realistic API response."""
    client = TellerClient()
    
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
"""Tests for sprig.teller_client module."""

import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch
import pytest

import requests

from sprig.teller_client import TellerClient, _is_rate_limit_error
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
        headers={"Content-Type": "application/json"},
        params=None,
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

    mock_make_request.assert_called_once_with("test_token", "/accounts/acc_456/transactions", params=None)
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
        headers={"Content-Type": "application/json"},
        params=None,
    )
    
    # Verify realistic response
    assert len(result) == 1
    assert result[0]["name"] == "Chase Sapphire Preferred"
    assert result[0]["type"] == "credit"
    assert result[0]["last_four"] == "1234"


def test_is_rate_limit_error_with_429():
    """Test _is_rate_limit_error returns True for 429 errors."""
    mock_response = Mock()
    mock_response.status_code = 429
    error = requests.HTTPError()
    error.response = mock_response
    assert _is_rate_limit_error(error) is True


def test_is_rate_limit_error_with_other_status():
    """Test _is_rate_limit_error returns False for non-429 errors."""
    mock_response = Mock()
    mock_response.status_code = 500
    error = requests.HTTPError()
    error.response = mock_response
    assert _is_rate_limit_error(error) is False


def test_is_rate_limit_error_with_non_http_error():
    """Test _is_rate_limit_error returns False for non-HTTP errors."""
    error = ValueError("not an HTTP error")
    assert _is_rate_limit_error(error) is False


@patch('requests.Session.get')
def test_make_request_with_params(mock_get, mock_certs):
    """Test _make_request passes params to session.get."""
    client = TellerClient()

    mock_response = Mock()
    mock_response.json.return_value = {"test": "data"}
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    params = {"from_date": "2024-01-01"}
    client._make_request("test_token", "/test/endpoint", params=params)

    mock_get.assert_called_once_with(
        "https://api.teller.io/test/endpoint",
        auth=("test_token", ""),
        headers={"Content-Type": "application/json"},
        params=params,
    )


@patch('requests.Session.get')
def test_make_request_retries_on_429(mock_get, mock_certs):
    """Test _make_request retries on 429 rate limit errors."""
    client = TellerClient()

    # First two calls fail with 429, third succeeds
    mock_response_429 = Mock()
    mock_response_429.status_code = 429
    error_429 = requests.HTTPError()
    error_429.response = mock_response_429
    mock_response_429.raise_for_status.side_effect = error_429

    mock_response_ok = Mock()
    mock_response_ok.json.return_value = {"success": True}
    mock_response_ok.raise_for_status.return_value = None

    mock_get.side_effect = [mock_response_429, mock_response_429, mock_response_ok]

    result = client._make_request("test_token", "/test/endpoint")

    assert result == {"success": True}
    assert mock_get.call_count == 3


@patch('sprig.teller_client.TellerClient._make_request')
def test_get_transactions_with_start_date(mock_make_request, mock_certs):
    """Test get_transactions passes start_date as from_date param."""
    client = TellerClient()

    mock_make_request.return_value = []

    start = date(2024, 4, 1)
    client.get_transactions("test_token", "acc_123", start_date=start)

    mock_make_request.assert_called_once_with(
        "test_token",
        "/accounts/acc_123/transactions",
        params={"from_date": "2024-04-01"},
    )


@patch('sprig.teller_client.TellerClient._make_request')
def test_get_transactions_without_start_date(mock_make_request, mock_certs):
    """Test get_transactions passes None params when no start_date."""
    client = TellerClient()

    mock_make_request.return_value = []

    client.get_transactions("test_token", "acc_123")

    mock_make_request.assert_called_once_with(
        "test_token",
        "/accounts/acc_123/transactions",
        params=None,
    )
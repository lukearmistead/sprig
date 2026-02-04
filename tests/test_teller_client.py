"""Tests for sprig.teller_client module."""

import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch
import pytest

import requests

from sprig.teller_client import TellerClient, _is_rate_limit_error


@pytest.fixture
def cert_files():
    """Create temporary certificate files."""
    temp_dir = Path(tempfile.mkdtemp())
    cert_path = temp_dir / "cert.pem"
    key_path = temp_dir / "key.pem"
    cert_path.write_text("dummy cert content")
    key_path.write_text("dummy key content")
    yield str(cert_path), str(key_path)


def test_teller_client_initialization(cert_files):
    cert_path, key_path = cert_files
    client = TellerClient(cert_path, key_path)

    assert client.base_url == "https://api.teller.io"
    assert client.session.cert == (cert_path, key_path)


@patch('requests.Session.get')
def test_make_request(mock_get, cert_files):
    client = TellerClient(*cert_files)

    mock_response = Mock()
    mock_response.json.return_value = {"test": "data"}
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    result = client._make_request("test_token", "/test/endpoint")

    mock_get.assert_called_once_with(
        "https://api.teller.io/test/endpoint",
        auth=("test_token", ""),
        headers={"Content-Type": "application/json"},
        params=None,
    )
    assert result == {"test": "data"}


@patch('requests.Session.get')
def test_make_request_http_error(mock_get, cert_files):
    client = TellerClient(*cert_files)

    mock_response = Mock()
    mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
    mock_get.return_value = mock_response

    with pytest.raises(requests.HTTPError, match="404 Not Found"):
        client._make_request("test_token", "/bad/endpoint")


@patch('sprig.teller_client.TellerClient._make_request')
def test_get_accounts(mock_make_request, cert_files):
    client = TellerClient(*cert_files)

    mock_accounts = [{"id": "acc_123", "name": "Test Account", "type": "depository", "currency": "USD", "status": "open"}]
    mock_make_request.return_value = mock_accounts

    result = client.get_accounts("test_token")

    mock_make_request.assert_called_once_with("test_token", "/accounts")
    assert result == mock_accounts


@patch('sprig.teller_client.TellerClient._make_request')
def test_get_transactions(mock_make_request, cert_files):
    client = TellerClient(*cert_files)

    mock_transactions = [{"id": "txn_123", "account_id": "acc_456", "amount": 25.50}]
    mock_make_request.return_value = mock_transactions

    result = client.get_transactions("test_token", "acc_456")

    mock_make_request.assert_called_once_with("test_token", "/accounts/acc_456/transactions", params=None)
    assert result == mock_transactions


def test_is_rate_limit_error_with_429():
    mock_response = Mock()
    mock_response.status_code = 429
    error = requests.HTTPError()
    error.response = mock_response
    assert _is_rate_limit_error(error) is True


def test_is_rate_limit_error_with_other_status():
    mock_response = Mock()
    mock_response.status_code = 500
    error = requests.HTTPError()
    error.response = mock_response
    assert _is_rate_limit_error(error) is False


def test_is_rate_limit_error_with_non_http_error():
    error = ValueError("not an HTTP error")
    assert _is_rate_limit_error(error) is False


@patch('requests.Session.get')
def test_make_request_with_params(mock_get, cert_files):
    client = TellerClient(*cert_files)

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
def test_make_request_retries_on_429(mock_get, cert_files):
    client = TellerClient(*cert_files)

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
def test_get_transactions_with_start_date(mock_make_request, cert_files):
    client = TellerClient(*cert_files)
    mock_make_request.return_value = []

    start = date(2024, 4, 1)
    client.get_transactions("test_token", "acc_123", start_date=start)

    mock_make_request.assert_called_once_with(
        "test_token",
        "/accounts/acc_123/transactions",
        params={"from_date": "2024-04-01"},
    )


@patch('sprig.teller_client.TellerClient._make_request')
def test_get_transactions_without_start_date(mock_make_request, cert_files):
    client = TellerClient(*cert_files)
    mock_make_request.return_value = []

    client.get_transactions("test_token", "acc_123")

    mock_make_request.assert_called_once_with(
        "test_token",
        "/accounts/acc_123/transactions",
        params=None,
    )

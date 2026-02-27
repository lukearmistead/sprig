"""Tests for sprig.fetch module."""

from datetime import date
from unittest.mock import Mock, patch

import pytest
import requests

from sprig.fetch import fetch_account, fetch_all, fetch_token


def test_fetch_account():
    mock_client = Mock()
    mock_client.get_transactions.return_value = [
        {
            "id": "txn_123",
            "account_id": "acc_456",
            "amount": 25.50,
            "description": "Test Transaction",
            "date": "2024-01-15",
            "type": "card_payment",
            "status": "posted",
        },
        {
            "id": "txn_124",
            "account_id": "acc_456",
            "amount": -10.00,
            "description": "Another Transaction",
            "date": "2024-01-16",
            "type": "ach",
            "status": "posted",
        },
    ]

    transactions = fetch_account(mock_client, "test_token", "acc_456")

    mock_client.get_transactions.assert_called_once_with("test_token", "acc_456", start_date=None)
    assert len(transactions) == 2
    assert transactions[0].id == "txn_123"
    assert transactions[1].id == "txn_124"


def test_fetch_token():
    mock_client = Mock()
    mock_client.get_accounts.return_value = [
        {
            "id": "acc_123",
            "name": "Test Account",
            "type": "depository",
            "currency": "USD",
            "status": "open",
        }
    ]
    mock_client.get_transactions.return_value = []

    results = list(fetch_token(mock_client, "test_token"))

    mock_client.get_accounts.assert_called_once_with("test_token")
    mock_client.get_transactions.assert_called_once_with("test_token", "acc_123", start_date=None)

    assert len(results) == 1
    account, transactions = results[0]
    assert account.id == "acc_123"
    assert account.name == "Test Account"
    assert account.type == "depository"
    assert transactions == []


def test_fetch_all():
    mock_client = Mock()
    mock_client.get_accounts.return_value = [
        {
            "id": "acc_123",
            "name": "Test Account",
            "type": "depository",
            "currency": "USD",
            "status": "open",
        }
    ]
    mock_client.get_transactions.return_value = []

    results = list(fetch_all(mock_client, ["token_1"]))

    mock_client.get_accounts.assert_called_once_with("token_1")
    assert len(results) == 1
    assert results[0][0].id == "acc_123"


def test_fetch_all_multiple_tokens():
    mock_client = Mock()
    mock_client.get_accounts.return_value = [
        {
            "id": "acc_123",
            "name": "Test Account",
            "type": "depository",
            "currency": "USD",
            "status": "open",
        }
    ]
    mock_client.get_transactions.return_value = []

    results = list(fetch_all(mock_client, ["token_1", "token_2"]))

    assert mock_client.get_accounts.call_count == 2
    mock_client.get_accounts.assert_any_call("token_1")
    mock_client.get_accounts.assert_any_call("token_2")
    assert len(results) == 2


def test_fetch_token_invalid_token():
    mock_client = Mock()

    mock_response = Mock()
    mock_response.status_code = 401
    error = requests.HTTPError()
    error.response = mock_response
    mock_client.get_accounts.side_effect = error

    results = list(fetch_token(mock_client, "invalid_token"))

    assert results == []


def test_fetch_token_skips_deleted_enrollment():
    mock_client = Mock()

    mock_response = Mock()
    mock_response.status_code = 404
    error = requests.HTTPError()
    error.response = mock_response
    mock_client.get_accounts.side_effect = error

    results = list(fetch_token(mock_client, "deleted_token_123456"))

    assert results == []


def test_fetch_token_other_http_error():
    mock_client = Mock()

    mock_response = Mock()
    mock_response.status_code = 500
    error = requests.HTTPError()
    error.response = mock_response
    mock_client.get_accounts.side_effect = error

    with pytest.raises(requests.HTTPError) as exc_info:
        list(fetch_token(mock_client, "test_token"))
    assert exc_info.value.response.status_code == 500


@patch("sprig.fetch.logger")
def test_fetch_all_with_invalid_tokens(mock_logger):
    mock_client = Mock()

    def mock_get_accounts(token):
        if token == "invalid_token_123456":
            mock_response = Mock()
            mock_response.status_code = 401
            error = requests.HTTPError()
            error.response = mock_response
            raise error
        return [
            {
                "id": f"acc_{token[:5]}",
                "name": "Test Account",
                "type": "depository",
                "currency": "USD",
                "status": "open",
            }
        ]

    mock_client.get_accounts.side_effect = mock_get_accounts
    mock_client.get_transactions.return_value = []

    tokens = ["valid_token", "invalid_token_123456", "another_valid"]
    results = list(fetch_all(mock_client, tokens))

    # Two valid tokens yield results, invalid one is skipped
    assert len(results) == 2
    warning_calls = [str(call) for call in mock_logger.warning.call_args_list]
    assert any("expired" in call.lower() for call in warning_calls)


@patch("sprig.fetch.logger")
def test_fetch_token_skips_gone_account(mock_logger):
    mock_client = Mock()

    mock_client.get_accounts.return_value = [
        {"id": "acc_gone", "name": "Gone Account", "type": "depository", "currency": "USD", "status": "open"},
        {"id": "acc_ok", "name": "OK Account", "type": "depository", "currency": "USD", "status": "open"},
    ]

    def mock_get_transactions(token, account_id, start_date=None):
        if account_id == "acc_gone":
            resp = Mock()
            resp.status_code = 410
            error = requests.HTTPError()
            error.response = resp
            raise error
        return [
            {"id": "txn_1", "account_id": account_id, "amount": 10.0, "description": "Test", "date": "2024-01-15", "type": "ach", "status": "posted"},
        ]

    mock_client.get_transactions.side_effect = mock_get_transactions

    results = list(fetch_token(mock_client, "test_token"))

    # Only acc_ok yields results (acc_gone is skipped)
    assert len(results) == 1
    account, transactions = results[0]
    assert account.id == "acc_ok"
    assert len(transactions) == 1
    assert transactions[0].id == "txn_1"

    warning_calls = [str(call) for call in mock_logger.warning.call_args_list]
    assert any("acc_gone" in call and "no longer available" in call for call in warning_calls)


def test_fetch_account_passes_from_date_to_api():
    mock_client = Mock()
    mock_client.get_transactions.return_value = [
        {
            "id": "txn_new",
            "account_id": "acc_456",
            "amount": -10.00,
            "description": "Recent Transaction",
            "date": "2024-02-15",
            "type": "ach",
            "status": "posted",
        },
    ]

    from_date = date(2024, 2, 1)
    transactions = fetch_account(mock_client, "test_token", "acc_456", from_date)

    mock_client.get_transactions.assert_called_once_with("test_token", "acc_456", start_date=from_date)
    assert len(transactions) == 1
    assert transactions[0].id == "txn_new"

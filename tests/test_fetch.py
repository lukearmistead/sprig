"""Tests for sprig.fetch module."""

import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch
import requests

from sprig.fetch import Fetcher


def test_fetch_account():
    mock_client = Mock()
    mock_db = Mock()

    mock_transactions = [
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

    mock_client.get_transactions.return_value = mock_transactions
    mock_db.sync_transaction.return_value = True

    fetcher = Fetcher(client=mock_client, db=mock_db, access_tokens=[])
    fetcher.fetch_account("test_token", "acc_456")

    mock_client.get_transactions.assert_called_once_with("test_token", "acc_456", start_date=None)
    assert mock_db.sync_transaction.call_count == 2

    calls = mock_db.sync_transaction.call_args_list
    assert calls[0][0][0].id == "txn_123"
    assert calls[1][0][0].id == "txn_124"


def test_fetch_token():
    mock_client = Mock()
    mock_db = Mock()

    mock_accounts = [
        {
            "id": "acc_123",
            "name": "Test Account",
            "type": "depository",
            "currency": "USD",
            "status": "open",
        }
    ]

    mock_client.get_accounts.return_value = mock_accounts
    mock_client.get_transactions.return_value = []
    mock_db.save_account.return_value = True

    fetcher = Fetcher(client=mock_client, db=mock_db, access_tokens=[])
    fetcher.fetch_token("test_token")

    mock_client.get_accounts.assert_called_once_with("test_token")
    mock_client.get_transactions.assert_called_once_with("test_token", "acc_123", start_date=None)

    mock_db.save_account.assert_called_once()
    inserted_account = mock_db.save_account.call_args[0][0]
    assert inserted_account.id == "acc_123"
    assert inserted_account.name == "Test Account"
    assert inserted_account.type == "depository"


def test_fetch_all():
    mock_client = Mock()
    mock_db = Mock()

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
    mock_db.save_account.return_value = True

    fetcher = Fetcher(client=mock_client, db=mock_db, access_tokens=["token_1"])
    fetcher.fetch_all()

    mock_client.get_accounts.assert_called_once_with("token_1")
    mock_db.save_account.assert_called_once()


def test_fetch_all_multiple_tokens():
    mock_client = Mock()
    mock_db = Mock()

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
    mock_db.save_account.return_value = True

    fetcher = Fetcher(client=mock_client, db=mock_db, access_tokens=["token_1", "token_2"])
    fetcher.fetch_all()

    assert mock_client.get_accounts.call_count == 2
    mock_client.get_accounts.assert_any_call("token_1")
    mock_client.get_accounts.assert_any_call("token_2")


def test_fetch_with_real_database():
    with tempfile.TemporaryDirectory() as temp_dir:
        from sprig.database import SprigDatabase

        db_path = Path(temp_dir) / "test.db"
        db = SprigDatabase(db_path)

        mock_client = Mock()
        mock_client.get_accounts.return_value = [
            {
                "id": "acc_integration",
                "name": "Integration Test Account",
                "type": "depository",
                "currency": "USD",
                "status": "open",
            }
        ]
        mock_client.get_transactions.return_value = [
            {
                "id": "txn_integration",
                "account_id": "acc_integration",
                "amount": 100.00,
                "description": "Integration Test Transaction",
                "date": "2024-01-15",
                "type": "deposit",
                "status": "posted",
            }
        ]

        fetcher = Fetcher(client=mock_client, db=db, access_tokens=[])
        fetcher.fetch_token("test_token")

        import sqlite3

        with sqlite3.connect(db_path) as conn:
            assert conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 1
            assert conn.execute(
                "SELECT name FROM accounts WHERE id = 'acc_integration'"
            ).fetchone()[0] == "Integration Test Account"


def test_fetch_token_invalid_token():
    mock_client = Mock()
    mock_db = Mock()

    mock_response = Mock()
    mock_response.status_code = 401
    error = requests.HTTPError()
    error.response = mock_response
    mock_client.get_accounts.side_effect = error

    fetcher = Fetcher(client=mock_client, db=mock_db, access_tokens=[])
    success = fetcher.fetch_token("invalid_token")

    assert success is False
    mock_db.save_account.assert_not_called()


def test_fetch_token_other_http_error():
    mock_client = Mock()
    mock_db = Mock()

    mock_response = Mock()
    mock_response.status_code = 500
    error = requests.HTTPError()
    error.response = mock_response
    mock_client.get_accounts.side_effect = error

    fetcher = Fetcher(client=mock_client, db=mock_db, access_tokens=[])
    try:
        fetcher.fetch_token("test_token")
        assert False, "Expected HTTPError to be raised"
    except requests.HTTPError as e:
        assert e.response.status_code == 500


@patch("sprig.fetch.logger")
def test_fetch_all_with_invalid_tokens(mock_logger):
    mock_client = Mock()
    mock_db = Mock()

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
    mock_db.save_account.return_value = True

    tokens = ["valid_token", "invalid_token_123456", "another_valid"]
    fetcher = Fetcher(client=mock_client, db=mock_db, access_tokens=tokens)
    fetcher.fetch_all()

    warning_calls = [str(call) for call in mock_logger.warning.call_args_list]
    assert any("invalid/expired" in call.lower() for call in warning_calls)


def test_fetch_account_with_cutoff_date():
    mock_client = Mock()
    mock_db = Mock()

    mock_transactions = [
        {
            "id": "txn_old",
            "account_id": "acc_456",
            "amount": 25.50,
            "description": "Old Transaction",
            "date": "2024-01-01",
            "type": "card_payment",
            "status": "posted",
        },
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

    mock_client.get_transactions.return_value = mock_transactions
    mock_db.sync_transaction.return_value = True

    from_date = date(2024, 2, 1)
    fetcher = Fetcher(from_date=from_date, client=mock_client, db=mock_db, access_tokens=[])
    fetcher.fetch_account("test_token", "acc_456")

    mock_client.get_transactions.assert_called_once_with("test_token", "acc_456", start_date=from_date)
    assert mock_db.sync_transaction.call_count == 1
    calls = mock_db.sync_transaction.call_args_list
    assert calls[0][0][0].id == "txn_new"

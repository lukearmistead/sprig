"""Tests for sprig.sync module."""

import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch
import requests

from sprig.sync import Syncer


def test_sync_account():
    """Test syncing transactions for a single account."""
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

    syncer = Syncer(client=mock_client, db=mock_db)
    syncer.sync_account("test_token", "acc_456")

    mock_client.get_transactions.assert_called_once_with("test_token", "acc_456")
    assert mock_db.sync_transaction.call_count == 2

    calls = mock_db.sync_transaction.call_args_list
    assert calls[0][0][0].id == "txn_123"
    assert calls[1][0][0].id == "txn_124"


def test_sync_token():
    """Test syncing accounts and their transactions for a single token."""
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

    syncer = Syncer(client=mock_client, db=mock_db)
    syncer.sync_token("test_token")

    mock_client.get_accounts.assert_called_once_with("test_token")
    mock_client.get_transactions.assert_called_once_with("test_token", "acc_123")

    mock_db.save_account.assert_called_once()
    inserted_account = mock_db.save_account.call_args[0][0]
    assert inserted_account.id == "acc_123"
    assert inserted_account.name == "Test Account"
    assert inserted_account.type == "depository"


@patch("sprig.sync.categorize_uncategorized_transactions")
@patch("sprig.sync.credentials")
def test_sync_all(mock_credentials, mock_categorize):
    """Test syncing all accounts for all access tokens."""
    mock_credentials.get_access_tokens.return_value = [
        Mock(token="token_1"),
        Mock(token="token_2"),
    ]

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
    mock_db.clear_all_categories.return_value = 0

    syncer = Syncer(client=mock_client, db=mock_db)
    syncer.sync_all()

    assert mock_client.get_accounts.call_count == 2
    mock_client.get_accounts.assert_any_call("token_1")
    mock_client.get_accounts.assert_any_call("token_2")

    mock_categorize.assert_called_once()


def test_sync_with_real_database():
    """Integration test with real database but mocked API client."""
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

        syncer = Syncer(client=mock_client, db=db)
        syncer.sync_token("test_token")

        import sqlite3

        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM accounts")
            account_count = cursor.fetchone()[0]
            assert account_count == 1

            cursor = conn.execute("SELECT COUNT(*) FROM transactions")
            transaction_count = cursor.fetchone()[0]
            assert transaction_count == 1

            cursor = conn.execute(
                "SELECT name FROM accounts WHERE id = 'acc_integration'"
            )
            account_name = cursor.fetchone()[0]
            assert account_name == "Integration Test Account"


def test_sync_token_invalid_token():
    """Test that invalid/expired tokens are handled gracefully."""
    mock_client = Mock()
    mock_db = Mock()

    mock_response = Mock()
    mock_response.status_code = 401
    error = requests.HTTPError()
    error.response = mock_response
    mock_client.get_accounts.side_effect = error

    syncer = Syncer(client=mock_client, db=mock_db)
    success = syncer.sync_token("invalid_token")

    assert success is False
    mock_db.save_account.assert_not_called()
    mock_client.get_accounts.assert_called_once_with("invalid_token")


def test_sync_token_other_http_error():
    """Test that non-401 HTTP errors are re-raised."""
    mock_client = Mock()
    mock_db = Mock()

    mock_response = Mock()
    mock_response.status_code = 500
    error = requests.HTTPError()
    error.response = mock_response
    mock_client.get_accounts.side_effect = error

    syncer = Syncer(client=mock_client, db=mock_db)
    try:
        syncer.sync_token("test_token")
        assert False, "Expected HTTPError to be raised"
    except requests.HTTPError as e:
        assert e.response.status_code == 500


@patch("sprig.sync.categorize_uncategorized_transactions")
@patch("sprig.sync.credentials")
@patch("sprig.sync.logger")
def test_sync_all_with_invalid_tokens(mock_logger, mock_credentials, mock_categorize):
    """Test sync_all handles invalid tokens and shows appropriate messages."""
    mock_credentials.get_access_tokens.return_value = [
        Mock(token="valid_token"),
        Mock(token="invalid_token_123456"),
        Mock(token="another_valid"),
    ]

    mock_client = Mock()
    mock_db = Mock()

    def mock_get_accounts(token):
        if token == "invalid_token_123456":
            mock_response = Mock()
            mock_response.status_code = 401
            error = requests.HTTPError()
            error.response = mock_response
            raise error
        else:
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

    syncer = Syncer(client=mock_client, db=mock_db)
    syncer.sync_all()

    # Should log warning for the invalid token
    warning_calls = [str(call) for call in mock_logger.warning.call_args_list]
    assert any("invalid/expired" in call.lower() for call in warning_calls)


@patch("sprig.sync.categorize_uncategorized_transactions")
@patch("sprig.sync.credentials")
@patch("sprig.sync.logger")
def test_sync_all_with_recategorize(mock_logger, mock_credentials, mock_categorize):
    """Test sync_all with recategorize=True clears categories before sync."""
    mock_credentials.get_access_tokens.return_value = [Mock(token="token_1")]

    mock_client = Mock()
    mock_db = Mock()

    mock_db.clear_all_categories.return_value = 10

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

    syncer = Syncer(client=mock_client, db=mock_db)
    syncer.sync_all(recategorize=True)

    mock_db.clear_all_categories.assert_called_once()
    mock_client.get_accounts.assert_called_once_with("token_1")
    mock_categorize.assert_called_once()


@patch("sprig.sync.categorize_uncategorized_transactions")
@patch("sprig.sync.credentials")
def test_sync_all_without_recategorize(mock_credentials, mock_categorize):
    """Test sync_all with recategorize=False does not clear categories."""
    mock_credentials.get_access_tokens.return_value = [Mock(token="token_1")]

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

    syncer = Syncer(client=mock_client, db=mock_db)
    syncer.sync_all()

    mock_db.clear_all_categories.assert_not_called()
    mock_client.get_accounts.assert_called_once_with("token_1")
    mock_categorize.assert_called_once()


def test_sync_account_with_cutoff_date():
    """Test syncing transactions with from_date filter."""
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
    syncer = Syncer(from_date=from_date, client=mock_client, db=mock_db)
    syncer.sync_account("test_token", "acc_456")

    mock_client.get_transactions.assert_called_once_with("test_token", "acc_456")

    assert mock_db.sync_transaction.call_count == 1
    calls = mock_db.sync_transaction.call_args_list
    assert calls[0][0][0].id == "txn_new"


@patch("sprig.sync.categorize_uncategorized_transactions")
@patch("sprig.sync.credentials")
@patch("sprig.sync.logger")
def test_sync_all_with_from_date_filter(mock_logger, mock_credentials, mock_categorize):
    """Test sync_all with from_date parameter."""
    mock_credentials.get_access_tokens.return_value = [Mock(token="token_1")]

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

    from_date = date(2024, 1, 1)
    syncer = Syncer(from_date=from_date, client=mock_client, db=mock_db)
    syncer.sync_all()

    mock_categorize.assert_called_once()

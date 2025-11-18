"""Tests for sprig.sync module."""

import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch
import requests

from sprig.sync import sync_all_accounts, sync_accounts_for_token, sync_transactions_for_account


def test_sync_transactions_for_account():
    """Test syncing transactions for a single account."""
    # Mock client and database
    mock_client = Mock()
    mock_db = Mock()

    # Mock transaction data from API
    mock_transactions = [
        {
            "id": "txn_123",
            "account_id": "acc_456",
            "amount": 25.50,
            "description": "Test Transaction",
            "date": "2024-01-15",
            "type": "card_payment",
            "status": "posted"
        },
        {
            "id": "txn_124",
            "account_id": "acc_456",
            "amount": -10.00,
            "description": "Another Transaction",
            "date": "2024-01-16",
            "type": "ach",
            "status": "posted"
        }
    ]

    mock_client.get_transactions.return_value = mock_transactions
    mock_db.insert_record.return_value = True

    # Call function
    sync_transactions_for_account(mock_client, mock_db, "test_token", "acc_456")

    # Verify API call
    mock_client.get_transactions.assert_called_once_with("test_token", "acc_456")

    # Verify database inserts (should have all Pydantic model fields)
    assert mock_db.insert_record.call_count == 2

    # Check that transactions were inserted (verify the call was made with transaction data)
    calls = mock_db.insert_record.call_args_list
    assert len(calls) == 2
    assert calls[0][0][0] == "transactions"  # Table name
    assert calls[0][0][1]["id"] == "txn_123"  # Transaction ID
    assert calls[1][0][0] == "transactions"  # Table name
    assert calls[1][0][1]["id"] == "txn_124"  # Transaction ID


def test_sync_accounts_for_token():
    """Test syncing accounts and their transactions for a single token."""
    # Mock client and database
    mock_client = Mock()
    mock_db = Mock()

    # Mock account data from API
    mock_accounts = [
        {
            "id": "acc_123",
            "name": "Test Account",
            "type": "depository",
            "currency": "USD",
            "status": "open"
        }
    ]

    mock_client.get_accounts.return_value = mock_accounts
    mock_client.get_transactions.return_value = []  # No transactions for simplicity
    mock_db.insert_record.return_value = True

    # Call function
    sync_accounts_for_token(mock_client, mock_db, "test_token")

    # Verify API calls
    mock_client.get_accounts.assert_called_once_with("test_token")
    mock_client.get_transactions.assert_called_once_with("test_token", "acc_123")

    # Verify account insert (should have all Pydantic model fields)
    account_calls = [call for call in mock_db.insert_record.call_args_list if call[0][0] == "accounts"]
    assert len(account_calls) == 1
    inserted_account = account_calls[0][0][1]
    assert inserted_account["id"] == "acc_123"
    assert inserted_account["name"] == "Test Account"
    assert inserted_account["type"] == "depository"


@patch('sprig.sync.categorize_uncategorized_transactions')
@patch('sprig.sync.SprigDatabase')
@patch('sprig.sync.TellerClient')
def test_sync_all_accounts(mock_teller_client_class, mock_database_class, mock_categorize):
    """Test syncing all accounts for all access tokens."""
    # Mock config
    mock_config = Mock()
    mock_config.access_tokens = ["token_1", "token_2"]
    mock_config.database_path = Path("/test/path")

    # Mock client and database instances
    mock_client = Mock()
    mock_db = Mock()
    mock_teller_client_class.return_value = mock_client
    mock_database_class.return_value = mock_db

    # Mock API responses
    mock_client.get_accounts.return_value = [
        {
            "id": "acc_123",
            "name": "Test Account",
            "type": "depository",
            "currency": "USD",
            "status": "open"
        }
    ]
    mock_client.get_transactions.return_value = []
    mock_db.insert_record.return_value = True

    # Call function
    sync_all_accounts(mock_config)

    # Verify client and database were created
    mock_teller_client_class.assert_called_once_with(mock_config)
    mock_database_class.assert_called_once_with(mock_config.database_path)

    # Verify get_accounts called for each token
    assert mock_client.get_accounts.call_count == 2
    mock_client.get_accounts.assert_any_call("token_1")
    mock_client.get_accounts.assert_any_call("token_2")

    # Verify categorization was called with default batch_size
    mock_categorize.assert_called_once_with(mock_config, mock_db, 10)


def test_sync_with_real_database():
    """Integration test with real database but mocked API client."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create real database
        from sprig.database import SprigDatabase
        db_path = Path(temp_dir) / "test.db"
        db = SprigDatabase(db_path)

        # Mock client
        mock_client = Mock()
        mock_client.get_accounts.return_value = [
            {
                "id": "acc_integration",
                "name": "Integration Test Account",
                "type": "depository",
                "currency": "USD",
                "status": "open"
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
                "status": "posted"
            }
        ]

        # Call sync function
        sync_accounts_for_token(mock_client, db, "test_token")

        # Verify data in database
        import sqlite3
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM accounts")
            account_count = cursor.fetchone()[0]
            assert account_count == 1

            cursor = conn.execute("SELECT COUNT(*) FROM transactions")
            transaction_count = cursor.fetchone()[0]
            assert transaction_count == 1

            cursor = conn.execute("SELECT name FROM accounts WHERE id = 'acc_integration'")
            account_name = cursor.fetchone()[0]
            assert account_name == "Integration Test Account"


def test_sync_accounts_for_token_invalid_token():
    """Test that invalid/expired tokens are handled gracefully."""
    # Mock client and database
    mock_client = Mock()
    mock_db = Mock()

    # Mock 401 Unauthorized error for invalid token
    mock_response = Mock()
    mock_response.status_code = 401
    error = requests.HTTPError()
    error.response = mock_response
    mock_client.get_accounts.side_effect = error

    # Call function
    result = sync_accounts_for_token(mock_client, mock_db, "invalid_token")

    # Should return False for invalid token
    assert not result

    # Should not insert anything to database
    mock_db.insert_record.assert_not_called()

    # Should have attempted to get accounts
    mock_client.get_accounts.assert_called_once_with("invalid_token")


def test_sync_accounts_for_token_other_http_error():
    """Test that non-401 HTTP errors are re-raised."""
    # Mock client and database
    mock_client = Mock()
    mock_db = Mock()

    # Mock 500 Internal Server Error
    mock_response = Mock()
    mock_response.status_code = 500
    error = requests.HTTPError()
    error.response = mock_response
    mock_client.get_accounts.side_effect = error

    # Should re-raise the error
    try:
        sync_accounts_for_token(mock_client, mock_db, "test_token")
        assert False, "Expected HTTPError to be raised"
    except requests.HTTPError as e:
        assert e.response.status_code == 500


@patch('sprig.sync.categorize_uncategorized_transactions')
@patch('sprig.sync.SprigDatabase')
@patch('sprig.sync.TellerClient')
@patch('sprig.sync.logger')
def test_sync_all_accounts_with_invalid_tokens(mock_logger, mock_teller_client_class, mock_database_class, mock_categorize):
    """Test sync_all_accounts handles invalid tokens and shows appropriate messages."""
    # Mock config with mix of valid and invalid tokens
    mock_config = Mock()
    mock_config.access_tokens = ["valid_token", "invalid_token_123456", "another_valid"]
    mock_config.database_path = Path("/test/path")

    # Mock client and database instances
    mock_client = Mock()
    mock_db = Mock()
    mock_teller_client_class.return_value = mock_client
    mock_database_class.return_value = mock_db

    # Mock API responses - second token returns 401 error
    def mock_get_accounts(token):
        if token == "invalid_token_123456":
            mock_response = Mock()
            mock_response.status_code = 401
            error = requests.HTTPError()
            error.response = mock_response
            raise error
        else:
            return [{
                "id": f"acc_{token[:5]}",
                "name": "Test Account",
                "type": "depository",
                "currency": "USD",
                "status": "open"
            }]

    mock_client.get_accounts.side_effect = mock_get_accounts
    mock_client.get_transactions.return_value = []
    mock_db.insert_record.return_value = True

    # Call function
    sync_all_accounts(mock_config)

    # Should log success message for valid tokens
    info_calls = [call for call in mock_logger.info.call_args_list if "Successfully synced 2 valid token(s)" in str(call)]
    assert len(info_calls) > 0

    # Should log warning about invalid tokens
    warning_calls = [call for call in mock_logger.warning.call_args_list if "invalid/expired token(s)" in str(call)]
    assert len(warning_calls) > 0


@patch('sprig.sync.categorize_uncategorized_transactions')
@patch('sprig.sync.SprigDatabase')
@patch('sprig.sync.TellerClient')
@patch('sprig.sync.logger')
def test_sync_all_accounts_with_recategorize(mock_logger, mock_teller_client_class, mock_database_class, mock_categorize):
    """Test sync_all_accounts with recategorize=True clears categories before sync."""
    # Mock config
    mock_config = Mock()
    mock_config.access_tokens = ["token_1"]
    mock_config.database_path = Path("/test/path")

    # Mock client and database instances
    mock_client = Mock()
    mock_db = Mock()
    mock_teller_client_class.return_value = mock_client
    mock_database_class.return_value = mock_db

    # Mock clear_all_categories to return 10 rows cleared
    mock_db.clear_all_categories.return_value = 10

    # Mock API responses
    mock_client.get_accounts.return_value = [
        {
            "id": "acc_123",
            "name": "Test Account",
            "type": "depository",
            "currency": "USD",
            "status": "open"
        }
    ]
    mock_client.get_transactions.return_value = []
    mock_db.insert_record.return_value = True

    # Call function with recategorize=True
    sync_all_accounts(mock_config, recategorize=True)

    # Verify clear_all_categories was called
    mock_db.clear_all_categories.assert_called_once()

    # Verify message about clearing categories was logged
    info_calls = [call for call in mock_logger.info.call_args_list if "Cleared categories for 10 transaction(s)" in str(call)]
    assert len(info_calls) > 0

    # Verify normal sync still happens
    mock_teller_client_class.assert_called_once_with(mock_config)
    mock_database_class.assert_called_once_with(mock_config.database_path)
    mock_client.get_accounts.assert_called_once_with("token_1")
    mock_categorize.assert_called_once_with(mock_config, mock_db, 10)


@patch('sprig.sync.categorize_uncategorized_transactions')
@patch('sprig.sync.SprigDatabase')
@patch('sprig.sync.TellerClient')
def test_sync_all_accounts_without_recategorize(mock_teller_client_class, mock_database_class, mock_categorize):
    """Test sync_all_accounts with recategorize=False does not clear categories."""
    # Mock config
    mock_config = Mock()
    mock_config.access_tokens = ["token_1"]
    mock_config.database_path = Path("/test/path")

    # Mock client and database instances
    mock_client = Mock()
    mock_db = Mock()
    mock_teller_client_class.return_value = mock_client
    mock_database_class.return_value = mock_db

    # Mock API responses
    mock_client.get_accounts.return_value = [
        {
            "id": "acc_123",
            "name": "Test Account",
            "type": "depository",
            "currency": "USD",
            "status": "open"
        }
    ]
    mock_client.get_transactions.return_value = []
    mock_db.insert_record.return_value = True

    # Call function with recategorize=False (default)
    sync_all_accounts(mock_config)

    # Verify clear_all_categories was NOT called
    mock_db.clear_all_categories.assert_not_called()

    # Verify normal sync still happens
    mock_teller_client_class.assert_called_once_with(mock_config)
    mock_database_class.assert_called_once_with(mock_config.database_path)
    mock_client.get_accounts.assert_called_once_with("token_1")
    mock_categorize.assert_called_once_with(mock_config, mock_db, 10)


def test_sync_transactions_with_cutoff_date():
    """Test syncing transactions with cutoff_date filter."""
    # Mock client and database
    mock_client = Mock()
    mock_db = Mock()

    # Mock transaction data with different dates
    mock_transactions = [
        {
            "id": "txn_old",
            "account_id": "acc_456",
            "amount": 25.50,
            "description": "Old Transaction",
            "date": "2024-01-01",
            "type": "card_payment",
            "status": "posted"
        },
        {
            "id": "txn_new",
            "account_id": "acc_456",
            "amount": -10.00,
            "description": "Recent Transaction",
            "date": "2024-02-15",
            "type": "ach",
            "status": "posted"
        }
    ]

    mock_client.get_transactions.return_value = mock_transactions
    mock_db.insert_record.return_value = True

    # Call function with cutoff_date filter
    cutoff_date = date(2024, 2, 1)
    sync_transactions_for_account(mock_client, mock_db, "test_token", "acc_456", cutoff_date=cutoff_date)

    # Verify API call
    mock_client.get_transactions.assert_called_once_with("test_token", "acc_456")

    # Verify only recent transaction was inserted (old one filtered out)
    assert mock_db.insert_record.call_count == 1
    calls = mock_db.insert_record.call_args_list
    assert calls[0][0][1]["id"] == "txn_new"



def test_sync_transactions_with_cutoff_date():
    """Test syncing transactions with cutoff_date filter."""
    # Mock client and database
    mock_client = Mock()
    mock_db = Mock()

    # Mock transaction data with different dates
    mock_transactions = [
        {
            "id": "txn_old",
            "account_id": "acc_456",
            "amount": 25.50,
            "description": "Old Transaction",
            "date": "2024-01-01",
            "type": "card_payment",
            "status": "posted"
        },
        {
            "id": "txn_new",
            "account_id": "acc_456",
            "amount": -10.00,
            "description": "Recent Transaction",
            "date": "2024-02-15",
            "type": "ach",
            "status": "posted"
        }
    ]

    mock_client.get_transactions.return_value = mock_transactions
    mock_db.insert_record.return_value = True

    # Call function with cutoff_date filter
    cutoff_date = date(2024, 2, 1)
    sync_transactions_for_account(mock_client, mock_db, "test_token", "acc_456", cutoff_date=cutoff_date)

    # Verify API call
    mock_client.get_transactions.assert_called_once_with("test_token", "acc_456")

    # Verify only recent transaction was inserted (old one filtered out)
    assert mock_db.insert_record.call_count == 1
    calls = mock_db.insert_record.call_args_list
    assert calls[0][0][1]["id"] == "txn_new"


@patch('sprig.sync.categorize_uncategorized_transactions')
@patch('sprig.sync.SprigDatabase')
@patch('sprig.sync.TellerClient')
@patch('sprig.sync.logger')
def test_sync_all_accounts_with_from_date_filter(
    mock_logger, mock_teller_client_class, mock_database_class, mock_categorize
):
    """Test sync_all_accounts with from_date parameter logs info."""
    # Mock config
    mock_config = Mock()
    mock_config.access_tokens = ["token_1"]
    mock_config.database_path = Path("/test/path")

    # Mock client and database instances
    mock_client = Mock()
    mock_db = Mock()
    mock_teller_client_class.return_value = mock_client
    mock_database_class.return_value = mock_db

    # Mock API responses
    mock_client.get_accounts.return_value = [
        {
            "id": "acc_123",
            "name": "Test Account",
            "type": "depository",
            "currency": "USD",
            "status": "open"
        }
    ]
    mock_client.get_transactions.return_value = []
    mock_db.insert_record.return_value = True

    # Call function with from_date parameter
    from_date = date(2024, 1, 1)
    sync_all_accounts(mock_config, from_date=from_date)

    # Verify filtering message was logged
    info_calls = [call for call in mock_logger.info.call_args_list if "Filtering transactions from 2024-01-01" in str(call)]
    assert len(info_calls) > 0

    # Verify categorization was called with default batch_size
    mock_categorize.assert_called_once_with(mock_config, mock_db, 10)

"""Tests for sprig.database module."""

import tempfile
from datetime import date
from pathlib import Path

from sprig.database import SprigDatabase


def test_database_initialization():
    """Test database file and table creation."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        SprigDatabase(db_path)
        
        assert db_path.exists()
        
        # Verify tables were created with correct schemas
        import sqlite3
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}
            assert "accounts" in tables
            assert "transactions" in tables
            
            # Verify accounts table schema
            cursor = conn.execute("PRAGMA table_info(accounts)")
            accounts_columns = {row[1] for row in cursor.fetchall()}
            expected_accounts_columns = {
                "id", "name", "type", "subtype", "institution", 
                "enrollment_id", "currency", "status", "last_four", 
                "links", "created_at"
            }
            assert accounts_columns == expected_accounts_columns
            
            # Verify transactions table schema
            cursor = conn.execute("PRAGMA table_info(transactions)")
            transactions_columns = {row[1] for row in cursor.fetchall()}
            expected_transactions_columns = {
                "id", "account_id", "amount", "description", "date", 
                "type", "status", "details", "running_balance", 
                "links", "inferred_category", "created_at"
            }
            assert transactions_columns == expected_transactions_columns


def test_insert_record():
    """Test record insertion."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        db = SprigDatabase(db_path)
        
        # Test account insertion
        account_data = {
            "id": "acc_123",
            "name": "Test Account",
            "type": "depository",
            "currency": "USD",
            "status": "open"
        }
        
        result = db.insert_record("accounts", account_data)
        assert result is True
        
        # Test transaction insertion
        transaction_data = {
            "id": "txn_123",
            "account_id": "acc_123", 
            "amount": 25.50,
            "description": "Test Transaction",
            "date": date(2024, 1, 15),
            "type": "card_payment",
            "status": "posted"
        }
        
        result = db.insert_record("transactions", transaction_data)
        assert result is True


def test_insert_record_with_json_fields():
    """Test record insertion with JSON fields."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        db = SprigDatabase(db_path)
        
        # Test account with JSON fields
        account_data = {
            "id": "acc_456",
            "name": "Test Account",
            "type": "depository",
            "currency": "USD",
            "status": "open",
            "institution": {"name": "Test Bank", "id": "bank_123"},
            "links": {"self": "https://api.example.com/accounts/acc_456"}
        }
        
        result = db.insert_record("accounts", account_data)
        assert result is True


def test_insert_record_handles_duplicates():
    """Test that INSERT OR REPLACE handles duplicate IDs."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        db = SprigDatabase(db_path)
        
        account_data = {
            "id": "acc_123",
            "name": "Original Account",
            "type": "depository", 
            "currency": "USD",
            "status": "open"
        }
        
        # Insert first time
        result1 = db.insert_record("accounts", account_data)
        assert result1 is True
        
        # Insert again with same ID but different data
        account_data["name"] = "Updated Account"
        result2 = db.insert_record("accounts", account_data)
        assert result2 is True
        
        # Verify only one record exists
        import sqlite3
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM accounts WHERE id = 'acc_123'")
            count = cursor.fetchone()[0]
            assert count == 1
            
            cursor = conn.execute("SELECT name FROM accounts WHERE id = 'acc_123'")
            name = cursor.fetchone()[0]
            assert name == "Updated Account"


def test_clear_all_categories():
    """Test clearing all transaction categories."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        db = SprigDatabase(db_path)
        
        # Insert test transactions with categories
        transaction_data = [
            {
                "id": "txn_1",
                "account_id": "acc_123",
                "amount": 25.50,
                "description": "Restaurant",
                "date": date(2024, 1, 15),
                "type": "card_payment",
                "status": "posted"
            },
            {
                "id": "txn_2", 
                "account_id": "acc_123",
                "amount": 50.00,
                "description": "Gas Station",
                "date": date(2024, 1, 16),
                "type": "card_payment",
                "status": "posted"
            }
        ]
        
        for txn in transaction_data:
            db.insert_record("transactions", txn)
        
        # Add categories to transactions
        db.update_transaction_category("txn_1", "dining")
        db.update_transaction_category("txn_2", "transport")
        
        # Verify categories were set
        import sqlite3
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM transactions WHERE inferred_category IS NOT NULL")
            categorized_count = cursor.fetchone()[0]
            assert categorized_count == 2
        
        # Clear all categories
        rows_cleared = db.clear_all_categories()
        assert rows_cleared == 2
        
        # Verify all categories are now NULL
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM transactions WHERE inferred_category IS NOT NULL")
            categorized_count = cursor.fetchone()[0]
            assert categorized_count == 0
            
            cursor = conn.execute("SELECT COUNT(*) FROM transactions WHERE inferred_category IS NULL")
            uncategorized_count = cursor.fetchone()[0]
            assert uncategorized_count == 2


def test_get_recent_transactions():
    """Test retrieving recent transactions."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        db = SprigDatabase(db_path)

        # Insert test account
        account_data = {
            "id": "acc_123",
            "name": "Test Checking",
            "type": "depository",
            "subtype": "checking",
            "currency": "USD",
            "status": "open",
            "last_four": "1234"
        }
        db.insert_record("accounts", account_data)

        # Insert test transactions
        transactions = [
            {
                "id": "txn_1",
                "account_id": "acc_123",
                "amount": -25.50,
                "description": "Coffee Shop",
                "date": date(2024, 1, 15),
                "type": "card_payment",
                "status": "posted",
                "details": {"counterparty": {"name": "Starbucks"}}
            },
            {
                "id": "txn_2",
                "account_id": "acc_123",
                "amount": -50.00,
                "description": "Gas Station",
                "date": date(2024, 1, 16),
                "type": "card_payment",
                "status": "posted",
                "details": {"counterparty": {"name": "Shell"}}
            },
            {
                "id": "txn_3",
                "account_id": "acc_123",
                "amount": 1000.00,
                "description": "Paycheck",
                "date": date(2024, 1, 17),
                "type": "ach",
                "status": "posted",
                "details": {"counterparty": {"name": "Employer"}}
            }
        ]

        for txn in transactions:
            db.insert_record("transactions", txn)

        # Add categories
        db.update_transaction_category("txn_1", "dining")
        db.update_transaction_category("txn_2", "transport")
        db.update_transaction_category("txn_3", "income")

        # Test: Get all recent transactions (default limit)
        results = db.get_recent_transactions(limit=10)
        assert len(results) == 3

        # Verify ordering (most recent first)
        assert results[0][0] == "txn_3"  # ID field
        assert results[1][0] == "txn_2"
        assert results[2][0] == "txn_1"

        # Test: Get with limit
        results = db.get_recent_transactions(limit=2)
        assert len(results) == 2
        assert results[0][0] == "txn_3"
        assert results[1][0] == "txn_2"

        # Test: Filter by category
        results = db.get_recent_transactions(limit=10, category="dining")
        assert len(results) == 1
        assert results[0][0] == "txn_1"
        assert results[0][4] == "dining"  # category field


def test_get_transaction_by_id():
    """Test retrieving a specific transaction by ID."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        db = SprigDatabase(db_path)

        # Insert test account
        account_data = {
            "id": "acc_123",
            "name": "Test Checking",
            "type": "depository",
            "subtype": "checking",
            "currency": "USD",
            "status": "open",
            "last_four": "1234"
        }
        db.insert_record("accounts", account_data)

        # Insert test transaction
        transaction_data = {
            "id": "txn_test",
            "account_id": "acc_123",
            "amount": -25.50,
            "description": "Coffee Shop",
            "date": date(2024, 1, 15),
            "type": "card_payment",
            "status": "posted",
            "details": {"counterparty": {"name": "Starbucks"}}
        }
        db.insert_record("transactions", transaction_data)
        db.update_transaction_category("txn_test", "dining")

        # Test: Get existing transaction
        result = db.get_transaction_by_id("txn_test")
        assert result is not None
        assert result[0] == "txn_test"  # id
        assert result[1] == "2024-01-15"  # date
        assert result[2] == "Coffee Shop"  # description
        assert result[3] == -25.50  # amount
        assert result[4] == "dining"  # inferred_category
        assert result[5] == "Starbucks"  # counterparty
        assert result[6] == "Test Checking"  # account_name
        assert result[7] == "checking"  # account_subtype
        assert result[8] == "1234"  # account_last_four

        # Test: Get non-existent transaction
        result = db.get_transaction_by_id("txn_nonexistent")
        assert result is None


def test_update_transaction_category():
    """Test updating transaction category."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        db = SprigDatabase(db_path)

        # Insert test transaction
        transaction_data = {
            "id": "txn_123",
            "account_id": "acc_123",
            "amount": -25.50,
            "description": "Test Transaction",
            "date": date(2024, 1, 15),
            "type": "card_payment",
            "status": "posted"
        }
        db.insert_record("transactions", transaction_data)

        # Test: Update category
        result = db.update_transaction_category("txn_123", "dining")
        assert result is True

        # Verify category was updated
        import sqlite3
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute(
                "SELECT inferred_category FROM transactions WHERE id = 'txn_123'"
            )
            category = cursor.fetchone()[0]
            assert category == "dining"

        # Test: Update to different category
        result = db.update_transaction_category("txn_123", "groceries")
        assert result is True

        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute(
                "SELECT inferred_category FROM transactions WHERE id = 'txn_123'"
            )
            category = cursor.fetchone()[0]
            assert category == "groceries"
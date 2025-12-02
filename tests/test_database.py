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
                "links", "inferred_category", "confidence", "created_at"
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


def test_update_transaction_category_with_confidence():
    """Test updating transaction category with confidence score."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        db = SprigDatabase(db_path)

        # Insert test account
        account_data = {
            "id": "acc_1",
            "name": "Test Checking",
            "type": "depository",
            "subtype": "checking",
            "institution": "Chase",
            "currency": "USD",
            "status": "open"
        }
        db.insert_record("accounts", account_data)

        # Insert test transaction
        transaction_data = {
            "id": "txn_1",
            "account_id": "acc_1",
            "amount": -25.50,
            "description": "COFFEE SHOP",
            "date": "2024-01-15",
            "type": "card_payment",
            "status": "posted"
        }
        db.insert_record("transactions", transaction_data)

        # Update category with confidence
        result = db.update_transaction_category("txn_1", "dining", 0.85)
        assert result is True

        # Verify category and confidence were set
        import sqlite3
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("SELECT inferred_category, confidence FROM transactions WHERE id = ?", ("txn_1",))
            category, confidence = cursor.fetchone()
            assert category == "dining"
            assert confidence == 0.85


def test_get_transaction_date_range():
    """Test getting the earliest and latest transaction dates for an account."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        db = SprigDatabase(db_path)

        account_data = {
            "id": "acc_1",
            "name": "Test Checking",
            "type": "depository",
            "currency": "USD",
            "status": "open"
        }
        db.insert_record("accounts", account_data)

        # Test with no transactions
        earliest, latest = db.get_transaction_date_range("acc_1")
        assert earliest is None
        assert latest is None

        # Insert transactions with different dates
        transactions = [
            {
                "id": "txn_1",
                "account_id": "acc_1",
                "amount": -25.50,
                "description": "Old Transaction",
                "date": "2024-01-15",
                "type": "card_payment",
                "status": "posted"
            },
            {
                "id": "txn_2",
                "account_id": "acc_1",
                "amount": -50.00,
                "description": "Recent Transaction",
                "date": "2024-03-20",
                "type": "card_payment",
                "status": "posted"
            },
            {
                "id": "txn_3",
                "account_id": "acc_1",
                "amount": -10.00,
                "description": "Middle Transaction",
                "date": "2024-02-10",
                "type": "card_payment",
                "status": "posted"
            }
        ]

        for txn in transactions:
            db.insert_record("transactions", txn)

        # Should return earliest and latest dates
        earliest, latest = db.get_transaction_date_range("acc_1")
        assert earliest == date(2024, 1, 15)
        assert latest == date(2024, 3, 20)

        # Test with different account (no transactions)
        earliest, latest = db.get_transaction_date_range("acc_2")
        assert earliest is None
        assert latest is None
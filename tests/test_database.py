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
                "links", "llm_category", "created_at"
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
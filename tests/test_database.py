"""Tests for sprig.database module."""

import sqlite3
import tempfile
from datetime import date
from pathlib import Path

from sprig.database import SprigDatabase
from sprig.models import TellerAccount


def test_database_initialization():
    """Test database file and table creation."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        SprigDatabase(db_path)

        assert db_path.exists()

        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}
            assert "accounts" in tables
            assert "transactions" in tables


def test_save_account():
    """Test account insertion and update."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db = SprigDatabase(Path(temp_dir) / "test.db")

        db.save_account(TellerAccount(
            id="acc_123",
            name="Test Account",
            type="depository",
            currency="USD",
            status="open",
        ))

        # Verify insert
        with sqlite3.connect(db.db_path) as conn:
            row = conn.execute("SELECT name FROM accounts WHERE id = 'acc_123'").fetchone()
            assert row[0] == "Test Account"

        # Update same account
        db.save_account(TellerAccount(
            id="acc_123",
            name="Updated Account",
            type="depository",
            currency="USD",
            status="open",
        ))

        # Verify update
        with sqlite3.connect(db.db_path) as conn:
            row = conn.execute("SELECT name FROM accounts WHERE id = 'acc_123'").fetchone()
            assert row[0] == "Updated Account"
            count = conn.execute("SELECT COUNT(*) FROM accounts WHERE id = 'acc_123'").fetchone()[0]
            assert count == 1


def test_save_account_with_json_fields():
    """Test account insertion with JSON fields."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db = SprigDatabase(Path(temp_dir) / "test.db")

        db.save_account(TellerAccount(
            id="acc_456",
            name="Test Account",
            type="depository",
            currency="USD",
            status="open",
            institution={"name": "Test Bank", "id": "bank_123"},
            links={"self": "https://api.example.com/accounts/acc_456"},
        ))

        with sqlite3.connect(db.db_path) as conn:
            row = conn.execute("SELECT institution FROM accounts WHERE id = 'acc_456'").fetchone()
            assert "Test Bank" in row[0]


def test_add_transaction():
    """Test transaction insertion."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db = SprigDatabase(Path(temp_dir) / "test.db")

        db.add_transaction({
            "id": "txn_123",
            "account_id": "acc_123",
            "amount": 25.50,
            "description": "Test Transaction",
            "date": date(2024, 1, 15),
            "type": "card_payment",
            "status": "posted",
        })

        with sqlite3.connect(db.db_path) as conn:
            row = conn.execute("SELECT description FROM transactions WHERE id = 'txn_123'").fetchone()
            assert row[0] == "Test Transaction"


def test_sync_transaction_preserves_category():
    """Test that sync_transaction preserves existing categories."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db = SprigDatabase(Path(temp_dir) / "test.db")

        # Insert and categorize a transaction
        db.add_transaction({
            "id": "txn_1",
            "account_id": "acc_1",
            "amount": -25.50,
            "description": "COFFEE SHOP",
            "date": "2024-01-15",
            "type": "card_payment",
            "status": "posted",
        })
        db.update_transaction_category("txn_1", "dining", 0.9)

        # Sync with updated description (simulating Teller update)
        from sprig.models import TellerTransaction
        txn = TellerTransaction(
            id="txn_1",
            account_id="acc_1",
            amount=-25.50,
            description="COFFEE SHOP - Updated",
            date=date(2024, 1, 15),
            type="card_payment",
            status="posted",
        )
        db.sync_transaction(txn)

        # Category should be preserved, description updated
        with sqlite3.connect(db.db_path) as conn:
            row = conn.execute(
                "SELECT description, inferred_category, confidence FROM transactions WHERE id = 'txn_1'"
            ).fetchone()
            assert row[0] == "COFFEE SHOP - Updated"
            assert row[1] == "dining"
            assert row[2] == 0.9


def test_clear_all_categories():
    """Test clearing all transaction categories."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db = SprigDatabase(Path(temp_dir) / "test.db")

        db.add_transaction({"id": "txn_1", "account_id": "acc_1", "amount": 25.50,
                           "description": "Test", "date": "2024-01-15", "type": "card_payment", "status": "posted"})
        db.add_transaction({"id": "txn_2", "account_id": "acc_1", "amount": 50.00,
                           "description": "Test", "date": "2024-01-16", "type": "card_payment", "status": "posted"})

        db.update_transaction_category("txn_1", "dining")
        db.update_transaction_category("txn_2", "transport")

        db.clear_all_categories()

        with sqlite3.connect(db.db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM transactions WHERE inferred_category IS NOT NULL").fetchone()[0]
            assert count == 0


def test_update_transaction_category():
    """Test updating transaction category with confidence."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db = SprigDatabase(Path(temp_dir) / "test.db")

        db.add_transaction({"id": "txn_1", "account_id": "acc_1", "amount": -25.50,
                           "description": "COFFEE", "date": "2024-01-15", "type": "card_payment", "status": "posted"})

        db.update_transaction_category("txn_1", "dining", 0.85)

        with sqlite3.connect(db.db_path) as conn:
            row = conn.execute("SELECT inferred_category, confidence FROM transactions WHERE id = 'txn_1'").fetchone()
            assert row[0] == "dining"
            assert row[1] == 0.85


def test_get_uncategorized_transactions():
    """Test fetching uncategorized transactions with account info."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db = SprigDatabase(Path(temp_dir) / "test.db")

        db.save_account(TellerAccount(id="acc_1", name="Chase Sapphire", type="credit",
                        subtype="credit_card", currency="USD", status="open", last_four="4242"))

        db.add_transaction({"id": "txn_1", "account_id": "acc_1", "amount": -25.50,
                           "description": "COFFEE", "date": "2024-01-15", "type": "card_payment", "status": "posted"})
        db.add_transaction({"id": "txn_2", "account_id": "acc_1", "amount": -50.00,
                           "description": "GAS", "date": "2024-01-16", "type": "card_payment", "status": "posted"})

        # Categorize one
        db.update_transaction_category("txn_1", "dining", 0.9)

        # Only uncategorized should be returned
        rows = db.get_uncategorized_transactions()
        assert len(rows) == 1
        assert rows[0]["id"] == "txn_2"
        assert rows[0]["account_name"] == "Chase Sapphire"
        assert rows[0]["account_subtype"] == "credit_card"
        assert rows[0]["account_last_four"] == "4242"


def test_get_transactions_for_export():
    """Test fetching all transactions for export."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db = SprigDatabase(Path(temp_dir) / "test.db")

        db.save_account(TellerAccount(id="acc_1", name="Test Account", type="depository",
                        subtype="checking", currency="USD", status="open"))

        db.add_transaction({"id": "txn_1", "account_id": "acc_1", "amount": -25.50,
                           "description": "Test", "date": "2024-01-15", "type": "card_payment", "status": "posted"})

        rows = db.get_transactions_for_export()
        assert len(rows) == 1
        assert rows[0][0] == "txn_1"  # id

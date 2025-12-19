"""Tests for sync categorization counting logic."""

import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

from sprig.database import SprigDatabase
from sprig.sync import categorize_uncategorized_transactions


def test_failed_categorization_counting():
    """Test that failed categorizations are counted correctly when Claude API returns empty results."""

    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        db = SprigDatabase(db_path)

        # Insert test transactions
        test_transactions = [
            {
                "id": "txn_success_1",
                "account_id": "acc_1",
                "amount": -25.50,
                "date": "2024-01-15",
                "description": "Coffee Shop",
                "status": "posted",
                "details": '{"counterparty": {"name": "Coffee Shop"}}',
                "type": "card_payment",
                "running_balance": 1000.0,
            },
            {
                "id": "txn_fail_1",
                "account_id": "acc_1",
                "amount": -45.00,
                "date": "2024-01-16",
                "description": "Gas Station",
                "status": "posted",
                "details": '{"counterparty": {"name": "Shell"}}',
                "type": "card_payment",
                "running_balance": 955.0,
            },
            {
                "id": "txn_fail_2",
                "account_id": "acc_1",
                "amount": -12.00,
                "date": "2024-01-17",
                "description": "Parking Meter",
                "status": "posted",
                "details": '{"counterparty": {"name": "City Parking"}}',
                "type": "card_payment",
                "running_balance": 910.0,
            },
        ]

        # Insert account
        db.insert_record(
            "accounts",
            {
                "id": "acc_1",
                "institution_id": "chase",
                "name": "Checking",
                "subtype": "checking",
                "last_four": "1234",
            },
        )

        # Insert transactions (all uncategorized)
        for txn_data in test_transactions:
            db.add_transaction(txn_data)

        # Mock categorizers
        with (
            patch("sprig.sync.CategoryConfig") as mock_config_class,
            patch("sprig.sync.ManualCategorizer") as mock_manual_class,
            patch("sprig.sync.ClaudeCategorizer") as mock_claude_class,
        ):
            # Mock category config
            mock_config = Mock()
            mock_config.manual_categories = []
            mock_config_class.load.return_value = mock_config

            # Mock manual categorizer (no manual overrides)
            mock_manual = Mock()
            mock_manual.categorize_batch.return_value = []
            mock_manual_class.return_value = mock_manual

            # Mock Claude categorizer - only categorize one transaction, fail the others
            from sprig.models import TransactionCategory
            mock_claude = Mock()
            mock_claude.categorize_batch.return_value = [
                TransactionCategory(transaction_id="txn_success_1", category="dining", confidence=0.95)
                # txn_fail_1 and txn_fail_2 are NOT in the results = failed categorization
            ]
            mock_claude_class.return_value = mock_claude

            # Run categorization with small batch size to test counting
            categorize_uncategorized_transactions(db, batch_size=25)

            # Verify database updates
            categorized_txns = db.connection.execute(
                "SELECT id, inferred_category FROM transactions WHERE inferred_category IS NOT NULL"
            ).fetchall()

            uncategorized_txns = db.connection.execute(
                "SELECT id FROM transactions WHERE inferred_category IS NULL"
            ).fetchall()

            # Should have 1 categorized and 2 uncategorized
            assert len(categorized_txns) == 1
            assert len(uncategorized_txns) == 2
            assert categorized_txns[0][0] == "txn_success_1"
            assert categorized_txns[0][1] == "dining"

            uncategorized_ids = {row[0] for row in uncategorized_txns}
            assert uncategorized_ids == {"txn_fail_1", "txn_fail_2"}


def test_all_transactions_fail_categorization():
    """Test counting when all transactions fail categorization (Claude returns empty dict)."""

    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        db = SprigDatabase(db_path)

        # Insert test transactions
        test_transactions = [
            {
                "id": "txn_fail_1",
                "account_id": "acc_1",
                "amount": -25.50,
                "date": "2024-01-15",
                "description": "Coffee Shop",
                "status": "posted",
                "details": '{"counterparty": {"name": "Coffee Shop"}}',
                "type": "card_payment",
                "running_balance": 1000.0,
            },
            {
                "id": "txn_fail_2",
                "account_id": "acc_1",
                "amount": -45.00,
                "date": "2024-01-16",
                "description": "Gas Station",
                "status": "posted",
                "details": '{"counterparty": {"name": "Shell"}}',
                "type": "card_payment",
                "running_balance": 955.0,
            },
        ]

        # Insert account
        db.insert_record(
            "accounts",
            {
                "id": "acc_1",
                "institution_id": "chase",
                "name": "Checking",
                "subtype": "checking",
                "last_four": "1234",
            },
        )

        # Insert transactions (all uncategorized)
        for txn_data in test_transactions:
            db.add_transaction(txn_data)

        # Mock categorizers
        with (
            patch("sprig.sync.CategoryConfig") as mock_config_class,
            patch("sprig.sync.ManualCategorizer") as mock_manual_class,
            patch("sprig.sync.ClaudeCategorizer") as mock_claude_class,
        ):
            # Mock category config
            mock_config = Mock()
            mock_config.manual_categories = []
            mock_config_class.load.return_value = mock_config

            # Mock manual categorizer (no manual overrides)
            mock_manual = Mock()
            mock_manual.categorize_batch.return_value = []
            mock_manual_class.return_value = mock_manual

            # Mock Claude categorizer - complete failure, empty results
            mock_claude = Mock()
            mock_claude.categorize_batch.return_value = []  # All transactions failed
            mock_claude_class.return_value = mock_claude

            # Run categorization
            categorize_uncategorized_transactions(db, batch_size=25)

            # Verify no transactions were categorized
            categorized_txns = db.connection.execute(
                "SELECT id FROM transactions WHERE inferred_category IS NOT NULL"
            ).fetchall()

            uncategorized_txns = db.connection.execute(
                "SELECT id FROM transactions WHERE inferred_category IS NULL"
            ).fetchall()

            # Should have 0 categorized and 2 uncategorized
            assert len(categorized_txns) == 0
            assert len(uncategorized_txns) == 2


def test_sync_preserves_existing_categories():
    """Test that sync_transaction preserves existing categories while updating transaction data."""

    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        db = SprigDatabase(db_path)

        # Insert account
        db.insert_record(
            "accounts",
            {
                "id": "acc_1",
                "name": "Checking",
                "type": "depository",
                "subtype": "checking",
                "currency": "USD",
                "status": "open",
                "last_four": "1234",
            },
        )

        # Add initial transaction
        initial_transaction = {
            "id": "txn_existing",
            "account_id": "acc_1",
            "amount": -25.50,
            "date": "2024-01-15",
            "description": "Coffee Shop",
            "status": "posted",
            "type": "card_payment",
            "running_balance": 1000.0,
        }
        db.add_transaction(initial_transaction)

        # Categorize the transaction
        db.update_transaction_category("txn_existing", "dining", 0.95)

        # Verify initial categorization
        import sqlite3

        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute(
                "SELECT inferred_category, confidence FROM transactions WHERE id = ?",
                ("txn_existing",),
            )
            category, confidence = cursor.fetchone()
            assert category == "dining"
            assert confidence == 0.95

        # Simulate sync with updated transaction data (new running balance, updated description)
        from sprig.models.teller import TellerTransaction

        updated_transaction = TellerTransaction(
            id="txn_existing",
            account_id="acc_1",
            amount=-25.50,
            date=date(2024, 1, 15),
            description="Coffee Shop Downtown",  # Updated description
            status="posted",
            type="card_payment",
            running_balance=950.0,  # Updated running balance
        )

        # Sync the transaction (should preserve category)
        result = db.sync_transaction(updated_transaction)
        assert result is True

        # Verify category and confidence are preserved
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute(
                "SELECT inferred_category, confidence, description, running_balance FROM transactions WHERE id = ?",
                ("txn_existing",),
            )
            category, confidence, description, running_balance = cursor.fetchone()

            # Category should be preserved
            assert category == "dining"
            assert confidence == 0.95

            # But raw data should be updated
            assert description == "Coffee Shop Downtown"
            assert running_balance == 950.0


def test_sync_adds_new_transaction_uncategorized():
    """Test that sync_transaction adds new transactions without categories."""

    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        db = SprigDatabase(db_path)

        # Insert account
        db.insert_record(
            "accounts",
            {
                "id": "acc_1",
                "name": "Checking",
                "type": "depository",
                "subtype": "checking",
                "currency": "USD",
                "status": "open",
                "last_four": "1234",
            },
        )

        # Sync a new transaction
        from sprig.models.teller import TellerTransaction

        new_transaction = TellerTransaction(
            id="txn_new",
            account_id="acc_1",
            amount=-45.00,
            date=date(2024, 1, 16),
            description="Gas Station",
            status="posted",
            type="card_payment",
            running_balance=955.0,
        )

        result = db.sync_transaction(new_transaction)
        assert result is True

        # Verify transaction was inserted with NULL category
        import sqlite3

        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute(
                "SELECT id, inferred_category, confidence FROM transactions WHERE id = ?",
                ("txn_new",),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "txn_new"
            assert row[1] is None  # inferred_category should be NULL
            assert row[2] is None  # confidence should be NULL

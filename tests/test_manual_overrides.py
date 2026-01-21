"""Tests for category overrides from config.yml."""

import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

import yaml

from sprig.database import SprigDatabase
from sprig.models import TellerAccount
from sprig.models.category_config import CategoryConfig
from sprig.categorizer import categorize_uncategorized_transactions


def test_category_config_loads_manual_categories():
    """Test that CategoryConfig can load manual_categories from YAML."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.yml"

        # Create config with manual categories
        config_data = {
            "categories": [
                {"name": "dining", "description": "Restaurants and food"},
                {"name": "groceries", "description": "Supermarkets"},
            ],
            "manual_categories": [
                {"transaction_id": "txn_123", "category": "dining"},
                {"transaction_id": "txn_456", "category": "groceries"},
            ],
        }

        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        # Load config
        category_config = CategoryConfig.load(config_path)

        # Verify manual categories were loaded
        assert category_config.manual_categories is not None
        assert len(category_config.manual_categories) == 2
        assert category_config.manual_categories[0].transaction_id == "txn_123"
        assert category_config.manual_categories[0].category == "dining"
        assert category_config.manual_categories[1].transaction_id == "txn_456"
        assert category_config.manual_categories[1].category == "groceries"


def test_category_config_allows_empty_manual_categories():
    """Test that CategoryConfig works without manual_categories section."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.yml"

        # Create config without manual categories
        config_data = {
            "categories": [
                {"name": "dining", "description": "Restaurants and food"},
                {"name": "groceries", "description": "Supermarkets"},
            ]
        }

        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        # Load config
        category_config = CategoryConfig.load(config_path)

        # Verify manual_categories is empty list
        assert category_config.manual_categories == []


def test_manual_overrides_applied_before_ai_categorization():
    """Test that manual overrides are applied before AI categorization runs.

    The new design applies manual overrides upfront via apply_manual_overrides(),
    which updates the DB directly. Then only truly uncategorized transactions
    are sent to Claude.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        config_path = Path(temp_dir) / "config.yml"

        # Create database with test transactions
        db = SprigDatabase(db_path)

        # Insert test account
        db.save_account(TellerAccount(
            id="acc_123",
            name="Test Checking",
            type="depository",
            subtype="checking",
            currency="USD",
            status="open",
            last_four="1234",
        ))

        # Insert uncategorized transactions
        transactions = [
            {
                "id": "txn_override_1",  # Has manual override
                "account_id": "acc_123",
                "amount": -25.50,
                "description": "Coffee Shop",
                "date": date(2024, 1, 15),
                "type": "card_payment",
                "status": "posted",
                "details": {"counterparty": {"name": "Starbucks"}},
            },
            {
                "id": "txn_override_2",  # Has manual override
                "account_id": "acc_123",
                "amount": -100.00,
                "description": "Grocery Store",
                "date": date(2024, 1, 16),
                "type": "card_payment",
                "status": "posted",
                "details": {"counterparty": {"name": "Whole Foods"}},
            },
            {
                "id": "txn_claude",  # No override, should use Claude
                "account_id": "acc_123",
                "amount": -50.00,
                "description": "Gas Station",
                "date": date(2024, 1, 17),
                "type": "card_payment",
                "status": "posted",
                "details": {"counterparty": {"name": "Shell"}},
            },
        ]

        for txn in transactions:
            db.add_transaction(txn)

        # Create config with manual overrides
        config_data = {
            "categories": [
                {"name": "dining", "description": "Restaurants"},
                {"name": "groceries", "description": "Supermarkets"},
                {"name": "transport", "description": "Gas and fuel"},
            ],
            "manual_categories": [
                {"transaction_id": "txn_override_1", "category": "dining"},
                {"transaction_id": "txn_override_2", "category": "groceries"},
            ],
        }

        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        test_category_config = CategoryConfig.load(config_path)

        from sprig.models import TransactionCategory

        with (
            patch("sprig.categorizer.CategoryConfig") as mock_category_config_class,
            patch("sprig.categorizer.categorize_in_batches") as mock_categorize_in_batches,
        ):
            mock_category_config_class.load.return_value = test_category_config

            # Mock AI categorization - should only be called for txn_claude
            mock_categorize_in_batches.return_value = [
                TransactionCategory(transaction_id="txn_claude", category="transport", confidence=0.9)
            ]

            categorize_uncategorized_transactions(db, batch_size=25)

            # Verify manual overrides were applied
            import sqlite3
            with sqlite3.connect(db_path) as conn:
                cursor = conn.execute(
                    "SELECT inferred_category, confidence FROM transactions WHERE id = 'txn_override_1'"
                )
                row = cursor.fetchone()
                assert row[0] == "dining"
                assert row[1] == 1.0  # Manual overrides have confidence 1.0

                cursor = conn.execute(
                    "SELECT inferred_category, confidence FROM transactions WHERE id = 'txn_override_2'"
                )
                row = cursor.fetchone()
                assert row[0] == "groceries"
                assert row[1] == 1.0

                cursor = conn.execute(
                    "SELECT inferred_category FROM transactions WHERE id = 'txn_claude'"
                )
                assert cursor.fetchone()[0] == "transport"

            # Verify AI was called only for the non-overridden transaction
            assert mock_categorize_in_batches.call_count == 1
            call_args = mock_categorize_in_batches.call_args
            transactions_sent = call_args[0][0]
            assert len(transactions_sent) == 1
            assert transactions_sent[0].id == "txn_claude"


def test_manual_override_replaces_existing_ai_category():
    """Test that apply_manual_overrides replaces existing AI-inferred categories."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        config_path = Path(temp_dir) / "config.yml"

        # Create database with test transactions
        db = SprigDatabase(db_path)

        # Insert test account
        db.save_account(TellerAccount(
            id="acc_123",
            name="Test Checking",
            type="depository",
            subtype="checking",
            currency="USD",
            status="open",
            last_four="1234",
        ))

        # Insert transaction WITH existing AI category (wrong category)
        txn_data = {
            "id": "txn_already_categorized",
            "account_id": "acc_123",
            "amount": -25.50,
            "description": "Coffee Shop",
            "date": date(2024, 1, 15),
            "type": "card_payment",
            "status": "posted",
            "details": {"counterparty": {"name": "Starbucks"}},
        }
        db.add_transaction(txn_data)

        # Set an AI-inferred category (simulating previous categorization)
        db.update_transaction_category("txn_already_categorized", "shopping", 0.7)

        # Verify the AI category is set
        import sqlite3
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute(
                "SELECT inferred_category, confidence FROM transactions WHERE id = 'txn_already_categorized'"
            )
            row = cursor.fetchone()
            assert row[0] == "shopping"
            assert row[1] == 0.7

        # Create config with manual override for this transaction
        config_data = {
            "categories": [
                {"name": "dining", "description": "Restaurants"},
                {"name": "shopping", "description": "Shopping"},
            ],
            "manual_categories": [
                {"transaction_id": "txn_already_categorized", "category": "dining"},
            ],
        }

        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        # Load the config and apply manual overrides
        category_config = CategoryConfig.load(config_path)

        from sprig.categorizer import apply_manual_overrides
        apply_manual_overrides(db, category_config)

        # Verify the manual override replaced the AI category
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute(
                "SELECT inferred_category, confidence FROM transactions WHERE id = 'txn_already_categorized'"
            )
            row = cursor.fetchone()
            assert row[0] == "dining", f"Expected 'dining' but got '{row[0]}'"
            assert row[1] == 1.0, f"Expected confidence 1.0 but got {row[1]}"


def test_apply_manual_overrides_skips_invalid_categories():
    """Test that apply_manual_overrides skips invalid category names."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        config_path = Path(temp_dir) / "config.yml"

        db = SprigDatabase(db_path)

        # Insert test account and transaction
        db.save_account(TellerAccount(
            id="acc_123",
            name="Test",
            type="depository",
            subtype="checking",
            currency="USD",
            status="open",
            last_four="1234",
        ))
        db.add_transaction({
            "id": "txn_test",
            "account_id": "acc_123",
            "amount": -25.50,
            "description": "Test",
            "date": date(2024, 1, 15),
            "type": "card_payment",
            "status": "posted",
            "details": {},
        })

        # Create config with invalid category
        config_data = {
            "categories": [
                {"name": "dining", "description": "Restaurants"},
            ],
            "manual_categories": [
                {"transaction_id": "txn_test", "category": "invalid_category"},
            ],
        }

        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        category_config = CategoryConfig.load(config_path)

        from sprig.categorizer import apply_manual_overrides
        apply_manual_overrides(db, category_config)

        # Verify the transaction was NOT updated (invalid category skipped)
        import sqlite3
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute(
                "SELECT inferred_category FROM transactions WHERE id = 'txn_test'"
            )
            row = cursor.fetchone()
            assert row[0] is None, f"Expected None but got '{row[0]}'"

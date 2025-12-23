"""Tests for category overrides from config.yml."""

import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

import yaml

from sprig.database import SprigDatabase
from sprig.models.category_config import CategoryConfig
from sprig.sync import categorize_uncategorized_transactions


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


def test_manual_categories_applied_before_claude_categorization():
    """Test that manual categories from config are applied before calling Claude."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        config_path = Path(temp_dir) / "config.yml"

        # Create database with test transactions
        db = SprigDatabase(db_path)

        # Insert test account
        account_data = {
            "id": "acc_123",
            "name": "Test Checking",
            "type": "depository",
            "subtype": "checking",
            "currency": "USD",
            "status": "open",
            "last_four": "1234",
        }
        db.insert_record("accounts", account_data)

        # Insert uncategorized transactions
        transactions = [
            {
                "id": "txn_override_1",  # Has category override
                "account_id": "acc_123",
                "amount": -25.50,
                "description": "Coffee Shop",
                "date": date(2024, 1, 15),
                "type": "card_payment",
                "status": "posted",
                "details": {"counterparty": {"name": "Starbucks"}},
            },
            {
                "id": "txn_override_2",  # Has category override
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

        # Create config with category overrides
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

        # Load the test category config
        test_category_config = CategoryConfig.load(config_path)

        # Import TransactionCategory for use in mocks
        from sprig.models import TransactionCategory

        # Mock CategoryConfig.load to return our test config
        # Mock the categorizer to verify it only receives non-overridden transactions
        with (
            patch("sprig.sync.CategoryConfig") as mock_category_config_class,
            patch("sprig.sync.categorize_inferentially") as mock_categorize_inferentially,
            patch("sprig.sync.categorize_manually") as mock_categorize_manually,
            patch("sprig.sync.credentials.setup_pydantic_ai_environment"),
        ):
            # Mock CategoryConfig.load to return our test config
            mock_category_config_class.load.return_value = test_category_config

            # Mock categorize_manually function
            manual_results = [
                TransactionCategory(transaction_id="txn_override_1", category="dining", confidence=1.0),
                TransactionCategory(transaction_id="txn_override_2", category="groceries", confidence=1.0),
            ]
            mock_categorize_manually.return_value = manual_results

            # Mock categorize_inferentially function
            mock_categorize_inferentially.return_value = [
                TransactionCategory(transaction_id="txn_claude", category="transport", confidence=0.9)
            ]

            # Run categorization
            categorize_uncategorized_transactions(db, batch_size=25)

            # Verify category overrides were applied
            import sqlite3

            with sqlite3.connect(db_path) as conn:
                cursor = conn.execute(
                    "SELECT inferred_category FROM transactions WHERE id = 'txn_override_1'"
                )
                assert cursor.fetchone()[0] == "dining"

                cursor = conn.execute(
                    "SELECT inferred_category FROM transactions WHERE id = 'txn_override_2'"
                )
                assert cursor.fetchone()[0] == "groceries"

                cursor = conn.execute(
                    "SELECT inferred_category FROM transactions WHERE id = 'txn_claude'"
                )
                assert cursor.fetchone()[0] == "transport"

            # Verify categorize_inferentially was called only once (for the non-overridden transaction)
            assert mock_categorize_inferentially.call_count == 1

            # Verify only the non-overridden transaction was sent to AI categorizer
            call_args = mock_categorize_inferentially.call_args
            transactions_sent = call_args[0][0]  # First positional argument
            assert len(transactions_sent) == 1
            assert transactions_sent[0].id == "txn_claude"


def test_category_override_validates_category():
    """Test that category overrides validate category at categorize time."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.yml"

        # Create config with invalid category override
        config_data = {
            "categories": [
                {"name": "dining", "description": "Restaurants"},
                {"name": "groceries", "description": "Supermarkets"},
            ],
            "manual_categories": [
                {"transaction_id": "txn_valid", "category": "dining"},
                {"transaction_id": "txn_invalid", "category": "invalid_category"}
            ],
        }

        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        # Loading should succeed - validation happens at categorize time
        category_config = CategoryConfig.load(config_path)
        assert len(category_config.manual_categories) == 2

        # Test that categorize_manually filters invalid categories
        from sprig.categorizer import categorize_manually
        from sprig.models import TellerTransaction
        from datetime import date

        # Create mock transactions
        transactions = [
            TellerTransaction(
                id="txn_valid",
                account_id="acc_123",
                amount=-25.50,
                description="Test",
                date=date(2024, 1, 15),
                type="card_payment",
                status="posted",
                details={}
            ),
            TellerTransaction(
                id="txn_invalid",
                account_id="acc_123",
                amount=-50.00,
                description="Test",
                date=date(2024, 1, 16),
                type="card_payment",
                status="posted",
                details={}
            )
        ]

        # Categorize should filter out invalid category
        results = categorize_manually(transactions, category_config)
        assert len(results) == 1
        assert results[0].transaction_id == "txn_valid"
        assert results[0].category == "dining"

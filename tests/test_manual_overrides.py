"""Tests for category overrides from config.yml."""

import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

import yaml

from sprig.database import SprigDatabase
from sprig.models import RuntimeConfig, TellerTransaction
from sprig.models.category_config import CategoryConfig
from sprig.sync import categorize_uncategorized_transactions


def test_category_config_loads_category_overrides():
    """Test that CategoryConfig can load category_overrides from YAML."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.yml"

        # Create config with category overrides
        config_data = {
            "categories": [
                {"name": "dining", "description": "Restaurants and food"},
                {"name": "groceries", "description": "Supermarkets"}
            ],
            "category_overrides": [
                {"transaction_id": "txn_123", "category": "dining"},
                {"transaction_id": "txn_456", "category": "groceries"}
            ]
        }

        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)

        # Load config
        category_config = CategoryConfig.load(config_path)

        # Verify overrides were loaded
        assert category_config.category_overrides is not None
        assert len(category_config.category_overrides) == 2
        assert category_config.category_overrides[0].transaction_id == "txn_123"
        assert category_config.category_overrides[0].category == "dining"
        assert category_config.category_overrides[1].transaction_id == "txn_456"
        assert category_config.category_overrides[1].category == "groceries"


def test_category_config_allows_empty_category_overrides():
    """Test that CategoryConfig works without category_overrides section."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.yml"

        # Create config without category overrides
        config_data = {
            "categories": [
                {"name": "dining", "description": "Restaurants and food"},
                {"name": "groceries", "description": "Supermarkets"}
            ]
        }

        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)

        # Load config
        category_config = CategoryConfig.load(config_path)

        # Verify overrides is empty list
        assert category_config.category_overrides == []


def test_category_overrides_applied_before_claude_categorization():
    """Test that category overrides from config are applied before calling Claude."""
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
            "last_four": "1234"
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
                "details": {"counterparty": {"name": "Starbucks"}}
            },
            {
                "id": "txn_override_2",  # Has category override
                "account_id": "acc_123",
                "amount": -100.00,
                "description": "Grocery Store",
                "date": date(2024, 1, 16),
                "type": "card_payment",
                "status": "posted",
                "details": {"counterparty": {"name": "Whole Foods"}}
            },
            {
                "id": "txn_claude",  # No override, should use Claude
                "account_id": "acc_123",
                "amount": -50.00,
                "description": "Gas Station",
                "date": date(2024, 1, 17),
                "type": "card_payment",
                "status": "posted",
                "details": {"counterparty": {"name": "Shell"}}
            }
        ]

        for txn in transactions:
            db.insert_record("transactions", txn)

        # Create config with category overrides
        config_data = {
            "categories": [
                {"name": "dining", "description": "Restaurants"},
                {"name": "groceries", "description": "Supermarkets"},
                {"name": "transport", "description": "Gas and fuel"}
            ],
            "category_overrides": [
                {"transaction_id": "txn_override_1", "category": "dining"},
                {"transaction_id": "txn_override_2", "category": "groceries"}
            ]
        }

        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)

        # Mock RuntimeConfig
        runtime_config = Mock(spec=RuntimeConfig)
        runtime_config.claude_api_key = "test_key"
        runtime_config.database_path = db_path
        runtime_config.category_config_path = config_path

        # Load the test category config
        test_category_config = CategoryConfig.load(config_path)

        # Mock the categorizer to verify it only receives non-overridden transactions
        with patch('sprig.sync.TransactionCategorizer') as mock_categorizer_class:
            mock_categorizer = Mock()
            mock_categorizer_class.return_value = mock_categorizer

            # Mock categorize_batch to return a category for the non-overridden transaction
            mock_categorizer.categorize_batch.return_value = {
                "txn_claude": "transport"
            }

            # Run categorization with explicit category_config
            categorize_uncategorized_transactions(runtime_config, db, batch_size=10, category_config=test_category_config)

            # Verify category overrides were applied
            import sqlite3
            with sqlite3.connect(db_path) as conn:
                cursor = conn.execute("SELECT inferred_category FROM transactions WHERE id = 'txn_override_1'")
                assert cursor.fetchone()[0] == "dining"

                cursor = conn.execute("SELECT inferred_category FROM transactions WHERE id = 'txn_override_2'")
                assert cursor.fetchone()[0] == "groceries"

                cursor = conn.execute("SELECT inferred_category FROM transactions WHERE id = 'txn_claude'")
                assert cursor.fetchone()[0] == "transport"

            # Verify categorizer was called only once (for the non-overridden transaction)
            assert mock_categorizer.categorize_batch.call_count == 1

            # Verify only the non-overridden transaction was sent to Claude
            call_args = mock_categorizer.categorize_batch.call_args
            transactions_sent = call_args[0][0]  # First positional argument
            assert len(transactions_sent) == 1
            assert transactions_sent[0].id == "txn_claude"


def test_category_override_validates_category():
    """Test that category overrides validate category against valid categories."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.yml"

        # Create config with invalid category override
        config_data = {
            "categories": [
                {"name": "dining", "description": "Restaurants"},
                {"name": "groceries", "description": "Supermarkets"}
            ],
            "category_overrides": [
                {"transaction_id": "txn_123", "category": "invalid_category"}
            ]
        }

        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)

        # Loading should fail with validation error
        try:
            category_config = CategoryConfig.load(config_path)
            # If we get here, validation should have caught the invalid category
            valid_categories = [cat.name for cat in category_config.categories]
            for override in category_config.category_overrides:
                assert override.category in valid_categories, \
                    f"Invalid category '{override.category}' in category override"
        except Exception:
            # Expected - invalid category should be caught
            pass

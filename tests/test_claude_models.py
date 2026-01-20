"""Tests for sprig.models.claude module."""

from unittest.mock import Mock

from sprig.models.claude import TransactionView


def test_transaction_view_from_db_row():
    """Test TransactionView.from_db_row() with all fields populated."""
    # Mock a sqlite3.Row object
    mock_row = Mock()
    mock_row.__getitem__ = lambda self, key: {
        "id": "txn_123",
        "date": "2024-01-15",
        "description": "COFFEE SHOP",
        "amount": -25.50,
        "account_name": "Chase Sapphire",
        "account_subtype": "credit_card",
        "counterparty": "Starbucks",
        "account_last_four": "4242",
    }[key]

    view = TransactionView.from_db_row(mock_row)

    assert view.id == "txn_123"
    assert view.date == "2024-01-15"
    assert view.description == "COFFEE SHOP"
    assert view.amount == -25.50
    assert view.account_name == "Chase Sapphire"
    assert view.account_subtype == "credit_card"
    assert view.counterparty == "Starbucks"
    assert view.account_last_four == "4242"
    assert view.inferred_category is None
    assert view.confidence is None


def test_transaction_view_from_db_row_with_nulls():
    """Test TransactionView.from_db_row() handling NULL values."""
    # Mock a sqlite3.Row with NULL counterparty and account_last_four
    mock_row = Mock()
    mock_row.__getitem__ = lambda self, key: {
        "id": "txn_456",
        "date": "2024-01-20",
        "description": "AMAZON",
        "amount": -100.00,
        "account_name": "Checking",
        "account_subtype": "checking",
        "counterparty": None,
        "account_last_four": None,
    }[key]

    view = TransactionView.from_db_row(mock_row)

    assert view.id == "txn_456"
    assert view.date == "2024-01-20"
    assert view.description == "AMAZON"
    assert view.amount == -100.00
    assert view.account_name == "Checking"
    assert view.account_subtype == "checking"
    assert view.counterparty is None
    assert view.account_last_four is None
    assert view.inferred_category is None
    assert view.confidence is None

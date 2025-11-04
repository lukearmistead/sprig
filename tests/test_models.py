"""Tests for sprig.models module."""

from datetime import date
from sprig.models import TellerAccount, TellerTransaction


def test_teller_account():
    """Test TellerAccount model validation."""
    account = TellerAccount(
        id="acc_123",
        name="Test Account",
        type="depository",
        currency="USD",
        status="open"
    )
    
    assert account.id == "acc_123"
    assert account.name == "Test Account"
    assert account.currency == "USD"


def test_teller_account_last_four():
    """Test last_four validation."""
    account = TellerAccount(
        id="acc_123",
        name="Test Account", 
        type="depository",
        currency="USD",
        status="open",
        last_four="1234"
    )
    
    assert account.last_four == "1234"


def test_teller_transaction():
    """Test TellerTransaction model validation."""
    transaction = TellerTransaction(
        id="txn_123",
        account_id="acc_123",
        amount=-25.50,
        description="Coffee Shop",
        date=date(2024, 1, 15),
        type="card_payment",
        status="posted"
    )
    
    assert transaction.id == "txn_123"
    assert transaction.amount == -25.50
    assert transaction.description == "Coffee Shop"
    assert transaction.date == date(2024, 1, 15)
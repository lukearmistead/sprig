"""Tests for sprig.models module."""

from datetime import date
from unittest.mock import patch, MagicMock

from sprig.models import TellerAccount, TellerTransaction
from sprig.models.config import Config
from sprig.models.claude import TransactionView
from sprig.categorize import categorize_inferentially


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


class TestConfigDefaults:
    MINIMAL_KWARGS = {
        "categories": [{"name": "general", "description": "general"}],
    }

    def test_minimal_config_gets_defaults(self):
        config = Config(**self.MINIMAL_KWARGS)
        assert config.batch_size == 50
        assert config.environment == "development"
        assert config.categorization_prompt == ""

    def test_explicit_values_override_defaults(self):
        config = Config(**self.MINIMAL_KWARGS, batch_size=25, environment="sandbox")
        assert config.batch_size == 25
        assert config.environment == "sandbox"



class TestCategorizationPromptFallback:
    SAMPLE_VIEW = TransactionView(
        id="txn_1", date="2024-01-01", description="Coffee", amount=-5.0
    )

    def _make_config(self, prompt=""):
        return Config(
            categories=[{"name": "dining", "description": "Restaurants"}],
            categorization_prompt=prompt,
        )

    @patch("sprig.categorize.AnthropicProvider")
    @patch("sprig.categorize.AnthropicModel")
    @patch("sprig.categorize.Agent")
    def test_uses_default_prompt_when_empty(self, mock_agent_cls, _model, _provider):
        mock_result = MagicMock()
        mock_result.output = []
        mock_agent_cls.return_value.run_sync.return_value = mock_result

        config = self._make_config(prompt="")
        categorize_inferentially([self.SAMPLE_VIEW], config)

        prompt_sent = mock_agent_cls.return_value.run_sync.call_args[0][0]
        assert "Analyze each transaction" in prompt_sent

    @patch("sprig.categorize.AnthropicProvider")
    @patch("sprig.categorize.AnthropicModel")
    @patch("sprig.categorize.Agent")
    def test_uses_custom_prompt_when_provided(self, mock_agent_cls, _model, _provider):
        mock_result = MagicMock()
        mock_result.output = []
        mock_agent_cls.return_value.run_sync.return_value = mock_result

        config = self._make_config(prompt="Custom: {categories} {transactions}")
        categorize_inferentially([self.SAMPLE_VIEW], config)

        prompt_sent = mock_agent_cls.return_value.run_sync.call_args[0][0]
        assert prompt_sent.startswith("Custom:")

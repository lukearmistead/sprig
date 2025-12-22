"""Tests for transaction categorization functionality.

This test file follows a test-first development approach for the Pydantic AI migration.
Tests define the expected behavior of the new function-based categorization API:
- categorize_manually(): Applies manual category overrides from config
- categorize_inferentially(): Uses AI agent for intelligent categorization

The functions being tested don't exist yet - this is intentional.
Implementation will follow in subsequent commits.
"""

from datetime import date
from unittest.mock import Mock, patch
import pytest

from sprig.categorizer import categorize_manually, categorize_inferentially
from sprig.models import TellerTransaction, TransactionCategory
from sprig.models.category_config import CategoryConfig
from sprig.models.credentials import ClaudeAPIKey


@pytest.fixture(autouse=True)
def mock_credentials():
    """Mock credentials for all tests."""
    with patch('sprig.categorizer.credentials.get_claude_api_key') as mock:
        mock.return_value = ClaudeAPIKey(value="sk-ant-api03-" + "a" * 95)
        yield mock


class TestBuildCategorizationPrompt:
    """Test prompt building functionality."""

    def test_build_prompt_includes_descriptions(self):
        """Test that prompt includes category descriptions."""

        transactions = [
            TellerTransaction(
                id="txn_123",
                account_id="acc_1",
                amount=25.50,
                description="Restaurant",
                date=date(2024, 1, 1),
                type="debit",
                status="posted"
            )
        ]

        # Load actual category config
        category_config = CategoryConfig.load()

        # Provide empty account info for test
        account_info = {}

        # Mock categorization_agent.run_sync to inspect the prompt
        with patch('sprig.categorizer.categorization_agent') as mock_agent:
            mock_agent.run_sync.return_value = Mock(data=[])

            # Call categorize_inferentially which should build the prompt internally
            categorize_inferentially(transactions, category_config, account_info)

            # Get the prompt from the call args
            call_args = mock_agent.run_sync.call_args
            prompt = str(call_args)

            # Should include actual categories from config
            assert "dining:" in prompt
            assert "groceries:" in prompt
            assert "txn_123" in prompt
            assert "Restaurant" in prompt


class TestInferentialCategorizerParsing:
    """Test parsing functionality of inferential categorizer."""

    def setup_method(self):
        """Set up test category config."""
        self.category_config = CategoryConfig.load()

    def test_validate_categories_valid_response(self):
        """Test validating valid response from agent."""
        transactions = [
            TellerTransaction(
                id="txn_123",
                account_id="acc_1",
                amount=25.50,
                description="Restaurant",
                date=date(2024, 1, 1),
                type="debit",
                status="posted"
            ),
            TellerTransaction(
                id="txn_456",
                account_id="acc_1",
                amount=50.00,
                description="Grocery Store",
                date=date(2024, 1, 2),
                type="debit",
                status="posted"
            )
        ]

        # Mock agent to return valid categories
        with patch('sprig.categorizer.categorization_agent') as mock_agent:
            mock_result = Mock()
            mock_result.data = [
                TransactionCategory(transaction_id="txn_123", category="dining", confidence=0.9),
                TransactionCategory(transaction_id="txn_456", category="groceries", confidence=0.85)
            ]
            mock_agent.run_sync.return_value = mock_result

            result = categorize_inferentially(transactions, self.category_config, {})

            assert len(result) == 2
            assert result[0].transaction_id == "txn_123"
            assert result[0].category == "dining"
            assert result[1].transaction_id == "txn_456"
            assert result[1].category == "groceries"

    def test_validate_categories_invalid_category(self):
        """Test that invalid categories are filtered out."""
        transactions = [
            TellerTransaction(
                id="txn_123",
                account_id="acc_1",
                amount=25.50,
                description="Restaurant",
                date=date(2024, 1, 1),
                type="debit",
                status="posted"
            ),
            TellerTransaction(
                id="txn_456",
                account_id="acc_1",
                amount=50.00,
                description="Unknown",
                date=date(2024, 1, 2),
                type="debit",
                status="posted"
            )
        ]

        # Mock agent to return mix of valid and invalid categories
        with patch('sprig.categorizer.categorization_agent') as mock_agent:
            mock_result = Mock()
            mock_result.data = [
                TransactionCategory(transaction_id="txn_123", category="dining", confidence=0.9),
                TransactionCategory(transaction_id="txn_456", category="invalid_category", confidence=0.5)
            ]
            mock_agent.run_sync.return_value = mock_result

            result = categorize_inferentially(transactions, self.category_config, {})

            # Invalid category should be filtered out
            assert len(result) == 1
            assert result[0].transaction_id == "txn_123"
            assert result[0].category == "dining"

    def test_validate_categories_mixed_valid_invalid(self):
        """Test mix of valid and invalid categories."""
        transactions = [
            TellerTransaction(
                id="txn_1",
                account_id="acc_1",
                amount=25.50,
                description="Restaurant",
                date=date(2024, 1, 1),
                type="debit",
                status="posted"
            ),
            TellerTransaction(
                id="txn_2",
                account_id="acc_1",
                amount=30.00,
                description="Unknown",
                date=date(2024, 1, 2),
                type="debit",
                status="posted"
            ),
            TellerTransaction(
                id="txn_3",
                account_id="acc_1",
                amount=45.00,
                description="Gas Station",
                date=date(2024, 1, 3),
                type="debit",
                status="posted"
            )
        ]

        # Mock agent to return mix of valid and invalid
        with patch('sprig.categorizer.categorization_agent') as mock_agent:
            mock_result = Mock()
            mock_result.data = [
                TransactionCategory(transaction_id="txn_1", category="dining", confidence=0.9),
                TransactionCategory(transaction_id="txn_2", category="wrong", confidence=0.5),
                TransactionCategory(transaction_id="txn_3", category="transport", confidence=0.85)
            ]
            mock_agent.run_sync.return_value = mock_result

            result = categorize_inferentially(transactions, self.category_config, {})

            # Only valid categories should be returned
            assert len(result) == 2
            assert result[0].transaction_id == "txn_1"
            assert result[0].category == "dining"
            assert result[1].transaction_id == "txn_3"
            assert result[1].category == "transport"


    def test_validate_categories_empty_list(self):
        """Test handling empty list."""
        transactions = []

        # Mock agent to return empty list
        with patch('sprig.categorizer.categorization_agent') as mock_agent:
            mock_result = Mock()
            mock_result.data = []
            mock_agent.run_sync.return_value = mock_result

            result = categorize_inferentially(transactions, self.category_config, {})

            assert result == []

    def test_validate_categories_all_invalid(self):
        """Test when all categories are invalid."""
        transactions = [
            TellerTransaction(
                id="txn_1",
                account_id="acc_1",
                amount=25.50,
                description="Unknown 1",
                date=date(2024, 1, 1),
                type="debit",
                status="posted"
            ),
            TellerTransaction(
                id="txn_2",
                account_id="acc_1",
                amount=30.00,
                description="Unknown 2",
                date=date(2024, 1, 2),
                type="debit",
                status="posted"
            )
        ]

        # Mock agent to return all invalid categories
        with patch('sprig.categorizer.categorization_agent') as mock_agent:
            mock_result = Mock()
            mock_result.data = [
                TransactionCategory(transaction_id="txn_1", category="fake1", confidence=0.5),
                TransactionCategory(transaction_id="txn_2", category="fake2", confidence=0.5)
            ]
            mock_agent.run_sync.return_value = mock_result

            result = categorize_inferentially(transactions, self.category_config, {})

            # All invalid, so empty list
            assert result == []




class TestCategorizeBatchIntegration:
    """Test full categorization workflow."""

    def test_categorize_batch_full_flow(self):
        """Test full categorization flow with mocked agent."""
        # Create test transactions with matching IDs
        transactions = [
            TellerTransaction(
                id="txn_ABC123",
                account_id="acc_1",
                amount=25.50,
                description="Restaurant",
                date="2024-01-01",
                type="debit",
                status="posted"
            ),
            TellerTransaction(
                id="txn_DEF456",
                account_id="acc_1",
                amount=45.00,
                description="Gas Station",
                date="2024-01-02",
                type="debit",
                status="posted"
            ),
            TellerTransaction(
                id="txn_GHI789",
                account_id="acc_1",
                amount=85.30,
                description="Supermarket",
                date="2024-01-03",
                type="debit",
                status="posted"
            )
        ]

        # Run categorization with account info
        category_config = CategoryConfig.load()
        account_info = {
            "txn_ABC123": {"name": "Checking", "subtype": "checking"},
            "txn_DEF456": {"name": "Checking", "subtype": "checking"},
            "txn_GHI789": {"name": "Checking", "subtype": "checking"}
        }

        # Mock categorization_agent.run_sync
        with patch('sprig.categorizer.categorization_agent') as mock_agent:
            mock_result = Mock()
            mock_result.data = [
                TransactionCategory(transaction_id="txn_ABC123", category="dining", confidence=0.9),
                TransactionCategory(transaction_id="txn_DEF456", category="transport", confidence=0.85),
                TransactionCategory(transaction_id="txn_GHI789", category="groceries", confidence=0.95)
            ]
            mock_agent.run_sync.return_value = mock_result

            result = categorize_inferentially(transactions, category_config, account_info)

            # Assert correct categories returned as list
            assert len(result) == 3
            assert result[0].transaction_id == "txn_ABC123"
            assert result[0].category == "dining"
            assert result[1].transaction_id == "txn_DEF456"
            assert result[1].category == "transport"
            assert result[2].transaction_id == "txn_GHI789"
            assert result[2].category == "groceries"

            # Verify agent was called
            mock_agent.run_sync.assert_called_once()
            call_args = mock_agent.run_sync.call_args
            # Verify transactions were passed in the call
            assert "txn_ABC123" in str(call_args)

    def test_categorize_batch_with_invalid_categories(self):
        """Test categorization with some invalid categories from agent."""
        # Create test transactions
        transactions = [
            TellerTransaction(
                id="txn_1",
                account_id="acc_1",
                amount=25.50,
                description="Restaurant",
                date="2024-01-01",
                type="debit",
                status="posted"
            )
        ]

        # Run categorization with empty account info
        category_config = CategoryConfig.load()
        account_info = {}

        # Mock agent to return mix of valid and invalid
        with patch('sprig.categorizer.categorization_agent') as mock_agent:
            mock_result = Mock()
            mock_result.data = [
                TransactionCategory(transaction_id="txn_1", category="dining", confidence=0.9),
                TransactionCategory(transaction_id="txn_2", category="invalid_cat", confidence=0.5),
                TransactionCategory(transaction_id="txn_3", category="groceries", confidence=0.85)
            ]
            mock_agent.run_sync.return_value = mock_result

            result = categorize_inferentially(transactions, category_config, account_info)

            # Assert invalid category is filtered out
            assert len(result) == 2
            assert result[0].transaction_id == "txn_1"
            assert result[0].category == "dining"
            assert result[1].transaction_id == "txn_3"
            assert result[1].category == "groceries"

    def test_categorize_with_account_info_context(self):
        """Test that account_info is passed to agent for context."""
        transactions = [
            TellerTransaction(
                id="txn_cc",
                account_id="acc_credit",
                amount=-50.00,  # Negative on credit card (payment/refund)
                description="Payment received",
                date="2024-01-01",
                type="card_payment",
                status="posted"
            )
        ]

        category_config = CategoryConfig.load()
        # Provide rich account info that should help with categorization
        account_info = {
            "txn_cc": {
                "name": "Chase Sapphire",
                "subtype": "credit_card",
                "last_four": "4567",
                "counterparty": "ACH Transfer"
            }
        }

        with patch('sprig.categorizer.categorization_agent') as mock_agent:
            mock_result = Mock()
            mock_result.data = [
                TransactionCategory(transaction_id="txn_cc", category="transfers", confidence=0.95)
            ]
            mock_agent.run_sync.return_value = mock_result

            result = categorize_inferentially(transactions, category_config, account_info)

            # Verify agent was called
            mock_agent.run_sync.assert_called_once()
            call_args = str(mock_agent.run_sync.call_args)

            # Verify account context was included in the call
            assert "credit_card" in call_args or "Chase Sapphire" in call_args

            # Verify categorization result
            assert len(result) == 1
            assert result[0].category == "transfers"


class TestManualCategorization:
    """Test manual categorization functionality."""

    def test_categorize_manually_basic(self):
        """Test basic manual categorization."""
        transactions = [
            TellerTransaction(
                id="txn_123",
                account_id="acc_1",
                amount=25.50,
                description="Restaurant",
                date=date(2024, 1, 1),
                type="debit",
                status="posted"
            ),
            TellerTransaction(
                id="txn_456",
                account_id="acc_1",
                amount=50.00,
                description="Grocery Store",
                date=date(2024, 1, 2),
                type="debit",
                status="posted"
            )
        ]

        # Load category config with manual categories
        category_config = CategoryConfig.load()
        # Simulate manual categories in config
        from sprig.models.category_config import ManualCategory
        category_config.manual_categories = [
            ManualCategory(transaction_id="txn_123", category="dining"),
            ManualCategory(transaction_id="txn_456", category="groceries")
        ]

        account_info = {}
        result = categorize_manually(transactions, category_config, account_info)

        assert len(result) == 2
        assert result[0].transaction_id == "txn_123"
        assert result[0].category == "dining"
        assert result[0].confidence == 1.0
        assert result[1].transaction_id == "txn_456"
        assert result[1].category == "groceries"
        assert result[1].confidence == 1.0

    def test_categorize_manually_filters_invalid_categories(self):
        """Test that manual categorization filters invalid categories."""
        transactions = [
            TellerTransaction(
                id="txn_valid",
                account_id="acc_1",
                amount=25.50,
                description="Restaurant",
                date=date(2024, 1, 1),
                type="debit",
                status="posted"
            ),
            TellerTransaction(
                id="txn_invalid",
                account_id="acc_1",
                amount=50.00,
                description="Unknown",
                date=date(2024, 1, 2),
                type="debit",
                status="posted"
            )
        ]

        category_config = CategoryConfig.load()
        from sprig.models.category_config import ManualCategory
        category_config.manual_categories = [
            ManualCategory(transaction_id="txn_valid", category="dining"),
            ManualCategory(transaction_id="txn_invalid", category="invalid_category")
        ]

        account_info = {}
        result = categorize_manually(transactions, category_config, account_info)

        # Only valid category should be returned
        assert len(result) == 1
        assert result[0].transaction_id == "txn_valid"
        assert result[0].category == "dining"

    def test_categorize_manually_empty_config(self):
        """Test manual categorization with no manual categories in config."""
        transactions = [
            TellerTransaction(
                id="txn_123",
                account_id="acc_1",
                amount=25.50,
                description="Restaurant",
                date=date(2024, 1, 1),
                type="debit",
                status="posted"
            )
        ]

        category_config = CategoryConfig.load()
        category_config.manual_categories = []

        account_info = {}
        result = categorize_manually(transactions, category_config, account_info)

        assert result == []

    def test_categorize_manually_only_matching_transactions(self):
        """Test that only transactions with matching IDs are categorized."""
        transactions = [
            TellerTransaction(
                id="txn_match",
                account_id="acc_1",
                amount=25.50,
                description="Restaurant",
                date=date(2024, 1, 1),
                type="debit",
                status="posted"
            ),
            TellerTransaction(
                id="txn_no_match",
                account_id="acc_1",
                amount=50.00,
                description="Grocery Store",
                date=date(2024, 1, 2),
                type="debit",
                status="posted"
            )
        ]

        category_config = CategoryConfig.load()
        from sprig.models.category_config import ManualCategory
        # Only configure one transaction
        category_config.manual_categories = [
            ManualCategory(transaction_id="txn_match", category="dining")
        ]

        account_info = {}
        result = categorize_manually(transactions, category_config, account_info)

        # Only the matching transaction should be categorized
        assert len(result) == 1
        assert result[0].transaction_id == "txn_match"
        assert result[0].category == "dining"

    def test_categorize_manually_confidence_always_max(self):
        """Test that manual categorization always returns confidence of 1.0."""
        transactions = [
            TellerTransaction(
                id="txn_123",
                account_id="acc_1",
                amount=25.50,
                description="Restaurant",
                date=date(2024, 1, 1),
                type="debit",
                status="posted"
            )
        ]

        category_config = CategoryConfig.load()
        from sprig.models.category_config import ManualCategory
        category_config.manual_categories = [
            ManualCategory(transaction_id="txn_123", category="dining")
        ]

        account_info = {}
        result = categorize_manually(transactions, category_config, account_info)

        # Manual categorization should always have 100% confidence
        assert len(result) == 1
        assert result[0].confidence == 1.0


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def setup_method(self):
        """Set up test category config."""
        self.category_config = CategoryConfig.load()

    def test_response_with_numeric_transaction_ids(self):
        """Test transaction IDs that are numeric strings."""
        transactions = [
            TellerTransaction(
                id="12345",
                account_id="acc_1",
                amount=25.50,
                description="Restaurant",
                date=date(2024, 1, 1),
                type="debit",
                status="posted"
            ),
            TellerTransaction(
                id="67890",
                account_id="acc_1",
                amount=45.00,
                description="Gas Station",
                date=date(2024, 1, 2),
                type="debit",
                status="posted"
            )
        ]

        with patch('sprig.categorizer.categorization_agent') as mock_agent:
            mock_result = Mock()
            mock_result.data = [
                TransactionCategory(transaction_id="12345", category="dining", confidence=0.9),
                TransactionCategory(transaction_id="67890", category="transport", confidence=0.85)
            ]
            mock_agent.run_sync.return_value = mock_result

            result = categorize_inferentially(transactions, self.category_config, {})

            assert len(result) == 2
            assert result[0].transaction_id == "12345"
            assert result[0].category == "dining"
            assert result[1].transaction_id == "67890"
            assert result[1].category == "transport"

    def test_response_with_special_characters(self):
        """Test transaction IDs with special characters."""
        transactions = [
            TellerTransaction(
                id="txn_abc-123",
                account_id="acc_1",
                amount=25.50,
                description="Restaurant",
                date=date(2024, 1, 1),
                type="debit",
                status="posted"
            ),
            TellerTransaction(
                id="txn_def_456",
                account_id="acc_1",
                amount=45.00,
                description="Gas Station",
                date=date(2024, 1, 2),
                type="debit",
                status="posted"
            )
        ]

        with patch('sprig.categorizer.categorization_agent') as mock_agent:
            mock_result = Mock()
            mock_result.data = [
                TransactionCategory(transaction_id="txn_abc-123", category="dining", confidence=0.9),
                TransactionCategory(transaction_id="txn_def_456", category="transport", confidence=0.85)
            ]
            mock_agent.run_sync.return_value = mock_result

            result = categorize_inferentially(transactions, self.category_config, {})

            assert len(result) == 2
            assert result[0].transaction_id == "txn_abc-123"
            assert result[0].category == "dining"
            assert result[1].transaction_id == "txn_def_456"
            assert result[1].category == "transport"

    def test_category_config_loads(self):
        """Test that category config loads properly."""
        category_config = CategoryConfig.load()
        category_names = {cat.name for cat in category_config.categories}
        assert "undefined" in category_names  # undefined should still be a valid category

"""Tests for transaction categorization functionality."""

from datetime import date
from unittest.mock import Mock, patch
import pytest

from sprig.categorizer import ClaudeCategorizer
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

        # Create categorizer to access _build_prompt
        categorizer = ClaudeCategorizer(category_config)

        # Provide empty account info for test
        account_info = {}
        prompt = categorizer._build_prompt(transactions, account_info)

        # Should include actual categories from config
        assert "dining:" in prompt
        assert "groceries:" in prompt
        assert "txn_123" in prompt
        assert "Restaurant" in prompt


class TestClaudeCategorizerParsing:
    """Test parsing functionality of ClaudeCategorizer."""

    def setup_method(self):
        """Set up test categorizer instance."""
        category_config = CategoryConfig.load()
        self.categorizer = ClaudeCategorizer(category_config)

    def test_validate_categories_valid_response(self):
        """Test validating valid response from Claude."""
        # Response should be list of TransactionCategory objects
        categories_list = [
            TransactionCategory(transaction_id="txn_123", category="dining", confidence=0.9),
            TransactionCategory(transaction_id="txn_456", category="groceries", confidence=0.85)
        ]

        result = self.categorizer._validate_categories(categories_list)

        assert len(result) == 2
        assert result[0].transaction_id == "txn_123"
        assert result[0].category == "dining"
        assert result[1].transaction_id == "txn_456"
        assert result[1].category == "groceries"

    def test_validate_categories_invalid_category(self):
        """Test that invalid categories are filtered out."""
        # Response with invalid category
        categories_list = [
            TransactionCategory(transaction_id="txn_123", category="dining", confidence=0.9),
            TransactionCategory(transaction_id="txn_456", category="invalid_category", confidence=0.5)
        ]

        result = self.categorizer._validate_categories(categories_list)

        # Invalid category should be filtered out
        assert len(result) == 1
        assert result[0].transaction_id == "txn_123"
        assert result[0].category == "dining"

    def test_validate_categories_mixed_valid_invalid(self):
        """Test mix of valid and invalid categories."""
        categories_list = [
            TransactionCategory(transaction_id="txn_1", category="dining", confidence=0.9),
            TransactionCategory(transaction_id="txn_2", category="wrong", confidence=0.5),
            TransactionCategory(transaction_id="txn_3", category="transport", confidence=0.85)
        ]

        result = self.categorizer._validate_categories(categories_list)

        # Only valid categories should be returned
        assert len(result) == 2
        assert result[0].transaction_id == "txn_1"
        assert result[0].category == "dining"
        assert result[1].transaction_id == "txn_3"
        assert result[1].category == "transport"


    def test_validate_categories_empty_list(self):
        """Test handling empty list."""
        categories_list = []

        result = self.categorizer._validate_categories(categories_list)

        assert result == []

    def test_validate_categories_all_invalid(self):
        """Test when all categories are invalid."""
        categories_list = [
            TransactionCategory(transaction_id="txn_1", category="fake1", confidence=0.5),
            TransactionCategory(transaction_id="txn_2", category="fake2", confidence=0.5)
        ]

        result = self.categorizer._validate_categories(categories_list)

        # All invalid, so empty list
        assert result == []




class TestCategorizeBatchIntegration:
    """Test full categorization workflow."""
    
    @patch('anthropic.Anthropic')
    def test_categorize_batch_full_flow(self, mock_anthropic):
        """Test full categorization flow with mocked Claude."""
        # Mock Claude API response
        mock_client = Mock()
        mock_anthropic.return_value = mock_client
        
        # The API response where content[0].text is the list of category objects
        mock_api_response = Mock()
        mock_api_response.model_dump.return_value = {
            "id": "msg_123",
            "type": "message",
            "role": "assistant", 
            "content": [
                {
                    "type": "text", 
                    "text": '{"transaction_id": "txn_ABC123", "category": "dining", "confidence": 0.9}, {"transaction_id": "txn_DEF456", "category": "transport", "confidence": 0.85}, {"transaction_id": "txn_GHI789", "category": "groceries", "confidence": 0.95}]'
                }
            ],
            "model": "claude-3-haiku",
            "usage": {}
        }
        mock_client.messages.create.return_value = mock_api_response
        
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
        categorizer = ClaudeCategorizer(category_config)
        account_info = {
            "txn_ABC123": {"name": "Checking", "subtype": "checking"},
            "txn_DEF456": {"name": "Checking", "subtype": "checking"},
            "txn_GHI789": {"name": "Checking", "subtype": "checking"}
        }
        result = categorizer.categorize_batch(transactions, account_info)

        # Assert correct categories returned as list
        assert len(result) == 3
        assert result[0].transaction_id == "txn_ABC123"
        assert result[0].category == "dining"
        assert result[1].transaction_id == "txn_DEF456"
        assert result[1].category == "transport"
        assert result[2].transaction_id == "txn_GHI789"
        assert result[2].category == "groceries"
        
        # Verify Claude was called with proper prompt
        mock_client.messages.create.assert_called_once()
        call_args = mock_client.messages.create.call_args
        assert "claude-haiku-4-5-20251001" in str(call_args)
        assert "txn_ABC123" in str(call_args)
    
    @patch('anthropic.Anthropic')
    def test_categorize_batch_with_invalid_categories(self, mock_anthropic):
        """Test categorization with some invalid categories from Claude."""
        # Mock Claude API response
        mock_client = Mock()
        mock_anthropic.return_value = mock_client
        
        # Response with mix of valid and invalid categories
        mock_api_response = Mock()
        mock_api_response.model_dump.return_value = {
            "id": "msg_123",
            "type": "message",
            "role": "assistant", 
            "content": [
                {
                    "type": "text", 
                    "text": '{"transaction_id": "txn_1", "category": "dining", "confidence": 0.9}, {"transaction_id": "txn_2", "category": "invalid_cat", "confidence": 0.5}, {"transaction_id": "txn_3", "category": "groceries", "confidence": 0.85}]'
                }
            ],
            "model": "claude-3-haiku",
            "usage": {}
        }
        mock_client.messages.create.return_value = mock_api_response
        
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
        categorizer = ClaudeCategorizer(category_config)
        account_info = {}
        result = categorizer.categorize_batch(transactions, account_info)

        # Assert invalid category is filtered out
        assert len(result) == 2
        assert result[0].transaction_id == "txn_1"
        assert result[0].category == "dining"
        assert result[1].transaction_id == "txn_3"
        assert result[1].category == "groceries"


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def setup_method(self):
        """Set up test categorizer instance."""
        category_config = CategoryConfig.load()
        self.categorizer = ClaudeCategorizer(category_config)

    def test_response_with_numeric_transaction_ids(self):
        """Test transaction IDs that are numeric strings."""
        categories_list = [
            TransactionCategory(transaction_id="12345", category="dining", confidence=0.9),
            TransactionCategory(transaction_id="67890", category="transport", confidence=0.85)
        ]

        result = self.categorizer._validate_categories(categories_list)

        assert len(result) == 2
        assert result[0].transaction_id == "12345"
        assert result[0].category == "dining"
        assert result[1].transaction_id == "67890"
        assert result[1].category == "transport"

    def test_response_with_special_characters(self):
        """Test transaction IDs with special characters."""
        categories_list = [
            TransactionCategory(transaction_id="txn_abc-123", category="dining", confidence=0.9),
            TransactionCategory(transaction_id="txn_def_456", category="transport", confidence=0.85)
        ]

        result = self.categorizer._validate_categories(categories_list)

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
"""Tests for transaction categorization functionality."""

from datetime import date
from unittest.mock import Mock, patch

from sprig.categorizer import (
    ClaudeCategorizer,
    build_categorization_prompt
)
from sprig.models import RuntimeConfig, TellerTransaction, TransactionCategory
from sprig.models.category_config import CategoryConfig


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
        prompt = build_categorization_prompt(transactions, account_info, category_config)
        
        # Should include actual categories from config
        assert "dining:" in prompt
        assert "groceries:" in prompt
        assert "txn_123" in prompt
        assert "Restaurant" in prompt


class TestClaudeCategorizerParsing:
    """Test parsing functionality of ClaudeCategorizer."""

    def setup_method(self):
        """Set up test categorizer instance."""
        # Mock runtime config
        self.runtime_config = Mock(spec=RuntimeConfig)
        self.runtime_config.claude_api_key = "test_key"

        # Create categorizer instance
        self.categorizer = ClaudeCategorizer(self.runtime_config)
    
    def test_validate_categories_valid_response(self):
        """Test validating valid response from Claude."""
        # Response should be list of TransactionCategory objects
        categories_list = [
            TransactionCategory(transaction_id="txn_123", category="dining"),
            TransactionCategory(transaction_id="txn_456", category="groceries")
        ]
        
        result = self.categorizer._validate_categories(categories_list)
        
        assert result == {"txn_123": "dining", "txn_456": "groceries"}
    
    def test_validate_categories_invalid_category(self):
        """Test fallback for invalid categories."""
        # Response with invalid category
        categories_list = [
            TransactionCategory(transaction_id="txn_123", category="dining"),
            TransactionCategory(transaction_id="txn_456", category="invalid_category")
        ]
        
        result = self.categorizer._validate_categories(categories_list)
        
        assert result == {"txn_123": "dining", "txn_456": None}
    
    def test_validate_categories_mixed_valid_invalid(self):
        """Test mix of valid and invalid categories."""
        categories_list = [
            TransactionCategory(transaction_id="txn_1", category="dining"),
            TransactionCategory(transaction_id="txn_2", category="wrong"),
            TransactionCategory(transaction_id="txn_3", category="transport")
        ]
        
        result = self.categorizer._validate_categories(categories_list)
        
        assert result == {
            "txn_1": "dining",
            "txn_2": None,
            "txn_3": "transport"
        }
    
    
    def test_validate_categories_empty_list(self):
        """Test handling empty list."""
        categories_list = []
        
        result = self.categorizer._validate_categories(categories_list)
        
        assert result == {}
    
    def test_validate_categories_all_invalid(self):
        """Test when all categories are invalid."""
        categories_list = [
            TransactionCategory(transaction_id="txn_1", category="fake1"),
            TransactionCategory(transaction_id="txn_2", category="fake2")
        ]
        
        result = self.categorizer._validate_categories(categories_list)
        
        assert result == {
            "txn_1": None,
            "txn_2": None
        }




class TestCategorizeBatchIntegration:
    """Test full categorization workflow."""
    
    def setup_method(self):
        """Set up test categorizer instance."""
        # Mock runtime config
        self.runtime_config = Mock(spec=RuntimeConfig)
        self.runtime_config.claude_api_key = "test_key"
    
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
                    "text": '{"transaction_id": "txn_ABC123", "category": "dining"}, {"transaction_id": "txn_DEF456", "category": "transport"}, {"transaction_id": "txn_GHI789", "category": "groceries"}]'
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
        categorizer = ClaudeCategorizer(self.runtime_config)
        account_info = {
            "txn_ABC123": {"name": "Checking", "subtype": "checking"},
            "txn_DEF456": {"name": "Checking", "subtype": "checking"},
            "txn_GHI789": {"name": "Checking", "subtype": "checking"}
        }
        result = categorizer.categorize_batch(transactions, account_info)
        
        # Assert correct categories returned
        assert result == {
            "txn_ABC123": "dining",
            "txn_DEF456": "transport",
            "txn_GHI789": "groceries"
        }
        
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
                    "text": '{"transaction_id": "txn_1", "category": "dining"}, {"transaction_id": "txn_2", "category": "invalid_cat"}, {"transaction_id": "txn_3", "category": "groceries"}]'
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
        categorizer = ClaudeCategorizer(self.runtime_config)
        account_info = {}
        result = categorizer.categorize_batch(transactions, account_info)
        
        # Assert invalid category gets None
        assert result == {
            "txn_1": "dining",
            "txn_2": None,
            "txn_3": "groceries"
        }


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def setup_method(self):
        """Set up test categorizer instance."""
        self.runtime_config = Mock(spec=RuntimeConfig)
        self.runtime_config.claude_api_key = "test_key"
        self.categorizer = ClaudeCategorizer(self.runtime_config)
    
    def test_response_with_numeric_transaction_ids(self):
        """Test transaction IDs that are numeric strings."""
        categories_list = [
            TransactionCategory(transaction_id="12345", category="dining"),
            TransactionCategory(transaction_id="67890", category="transport")
        ]
        
        result = self.categorizer._validate_categories(categories_list)
        
        assert result == {"12345": "dining", "67890": "transport"}
    
    def test_response_with_special_characters(self):
        """Test transaction IDs with special characters."""
        categories_list = [
            TransactionCategory(transaction_id="txn_abc-123", category="dining"),
            TransactionCategory(transaction_id="txn_def_456", category="transport")
        ]
        
        result = self.categorizer._validate_categories(categories_list)
        
        assert result == {"txn_abc-123": "dining", "txn_def_456": "transport"}
    
    def test_category_config_loads(self):
        """Test that category config loads properly."""
        category_config = CategoryConfig.load()
        category_names = {cat.name for cat in category_config.categories}
        assert "undefined" in category_names  # undefined should still be a valid category
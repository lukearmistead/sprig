"""Tests for transaction categorization functionality."""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path
import tempfile
import yaml

from sprig.categorizer import (
    load_categories, 
    get_category_names, 
    TransactionCategorizer,
    build_categorization_prompt,
    FALLBACK_CATEGORY
)
from sprig.models import RuntimeConfig, TellerTransaction, ClaudeResponse, ClaudeContentBlock, TransactionCategory


class TestLoadCategories:
    """Test category loading functionality."""
    
    def test_load_categories_valid_config(self):
        """Test loading categories from valid config file."""
        categories = load_categories()
        assert isinstance(categories, dict)
        assert "dining" in categories
        assert "groceries" in categories
        assert "undefined" in categories
        assert all(isinstance(desc, str) for desc in categories.values())
    
    def test_load_categories_missing_section(self):
        """Test error when config missing categories section."""
        # Create temp config without categories section
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump({"other_section": "data"}, f)
            temp_path = Path(f.name)
        
        with pytest.raises(ValueError, match="config.yml must contain a 'categories' section"):
            load_categories(temp_path)
    
    def test_load_categories_invalid_values(self):
        """Test error when category values are not strings."""
        # Create temp config with non-string values
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump({"categories": {"dining": "Restaurant", "invalid": 123}}, f)
            temp_path = Path(f.name)
        
        with pytest.raises(ValueError, match="All category descriptions must be strings"):
            load_categories(temp_path)


class TestGetCategoryNames:
    """Test category name extraction."""
    
    def test_get_category_names_with_dict(self):
        """Test getting names from provided dict."""
        categories = {"dining": "Restaurants", "fuel": "Gas stations"}
        names = get_category_names(categories)
        assert names == ["dining", "fuel"]
    
    def test_get_category_names_loads_config(self):
        """Test getting names loads from config when not provided."""
        names = get_category_names()
        assert isinstance(names, list)
        assert "dining" in names
        assert "groceries" in names


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
                date="2024-01-01",
                type="debit",
                status="posted"
            )
        ]
        categories = {"dining": "Restaurants and food delivery", "fuel": "Gas stations"}
        
        prompt = build_categorization_prompt(transactions, categories)
        
        assert "dining: Restaurants and food delivery" in prompt
        assert "fuel: Gas stations" in prompt
        assert "txn_123" in prompt
        assert "Restaurant" in prompt


class TestTransactionCategorizerParsing:
    """Test parsing functionality of TransactionCategorizer."""
    
    def setup_method(self):
        """Set up test categorizer instance."""
        # Mock runtime config
        self.runtime_config = Mock(spec=RuntimeConfig)
        self.runtime_config.claude_api_key = "test_key"
        
        # Create categorizer instance
        self.categorizer = TransactionCategorizer(self.runtime_config)
    
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
        
        assert result == {"txn_123": "dining", "txn_456": FALLBACK_CATEGORY}
    
    def test_validate_categories_mixed_valid_invalid(self):
        """Test mix of valid and invalid categories."""
        categories_list = [
            TransactionCategory(transaction_id="txn_1", category="dining"),
            TransactionCategory(transaction_id="txn_2", category="wrong"),
            TransactionCategory(transaction_id="txn_3", category="fuel")
        ]
        
        result = self.categorizer._validate_categories(categories_list)
        
        assert result == {
            "txn_1": "dining",
            "txn_2": FALLBACK_CATEGORY,
            "txn_3": "fuel"
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
            "txn_1": FALLBACK_CATEGORY,
            "txn_2": FALLBACK_CATEGORY
        }


class TestClaudeResponseUnpacking:
    """Test extracting data from ClaudeResponse."""
    
    def test_claude_response_unpacking(self):
        """Test extracting categories from ClaudeResponse content."""
        # The content[0].text contains list of TransactionCategory objects
        mock_response = ClaudeResponse(
            id="msg_123",
            type="message", 
            role="assistant",
            content=[
                ClaudeContentBlock(
                    type="text",
                    text=[
                        TransactionCategory(transaction_id="txn_ABC123", category="dining"),
                        TransactionCategory(transaction_id="txn_DEF456", category="groceries"),
                        TransactionCategory(transaction_id="txn_GHI789", category="fuel")
                    ]
                )
            ],
            model="claude-3-haiku",
            usage="test"
        )
        
        # Extract categories from content[0].text
        categories_list = mock_response.content[0].text
        
        # Verify structure
        assert len(categories_list) == 3
        assert categories_list[0].transaction_id == "txn_ABC123"
        assert categories_list[0].category == "dining"
        assert categories_list[1].transaction_id == "txn_DEF456"
        assert categories_list[1].category == "groceries"
        assert categories_list[2].transaction_id == "txn_GHI789"
        assert categories_list[2].category == "fuel"


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
                    "text": [
                        {"transaction_id": "txn_ABC123", "category": "dining"},
                        {"transaction_id": "txn_DEF456", "category": "fuel"},
                        {"transaction_id": "txn_GHI789", "category": "groceries"}
                    ]
                }
            ],
            "model": "claude-3-haiku",
            "usage": "test"
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
        
        # Run categorization
        categorizer = TransactionCategorizer(self.runtime_config)
        result = categorizer.categorize_batch(transactions)
        
        # Assert correct categories returned
        assert result == {
            "txn_ABC123": "dining",
            "txn_DEF456": "fuel",
            "txn_GHI789": "groceries"
        }
        
        # Verify Claude was called with proper prompt
        mock_client.messages.create.assert_called_once()
        call_args = mock_client.messages.create.call_args
        assert "claude-3-haiku-20240307" in str(call_args)
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
                    "text": [
                        {"transaction_id": "txn_1", "category": "dining"},
                        {"transaction_id": "txn_2", "category": "invalid_cat"},
                        {"transaction_id": "txn_3", "category": "groceries"}
                    ]
                }
            ],
            "model": "claude-3-haiku",
            "usage": "test"
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
        
        # Run categorization
        categorizer = TransactionCategorizer(self.runtime_config)
        result = categorizer.categorize_batch(transactions)
        
        # Assert invalid category gets fallback
        assert result == {
            "txn_1": "dining",
            "txn_2": FALLBACK_CATEGORY,
            "txn_3": "groceries"
        }


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def setup_method(self):
        """Set up test categorizer instance."""
        self.runtime_config = Mock(spec=RuntimeConfig)
        self.runtime_config.claude_api_key = "test_key"
        self.categorizer = TransactionCategorizer(self.runtime_config)
    
    def test_response_with_numeric_transaction_ids(self):
        """Test transaction IDs that are numeric strings."""
        categories_list = [
            TransactionCategory(transaction_id="12345", category="dining"),
            TransactionCategory(transaction_id="67890", category="fuel")
        ]
        
        result = self.categorizer._validate_categories(categories_list)
        
        assert result == {"12345": "dining", "67890": "fuel"}
    
    def test_response_with_special_characters(self):
        """Test transaction IDs with special characters."""
        categories_list = [
            TransactionCategory(transaction_id="txn_abc-123", category="dining"),
            TransactionCategory(transaction_id="txn_def_456", category="fuel")
        ]
        
        result = self.categorizer._validate_categories(categories_list)
        
        assert result == {"txn_abc-123": "dining", "txn_def_456": "fuel"}
    
    def test_constants_values(self):
        """Test that constants have expected values."""
        assert FALLBACK_CATEGORY == "undefined"
        
        # Verify undefined is actually a valid category
        categories = load_categories()
        assert FALLBACK_CATEGORY in categories
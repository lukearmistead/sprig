"""Tests for Claude API response models."""

import pytest
from pydantic import ValidationError

from sprig.models.claude import ClaudeResponse, ClaudeContentBlock, TransactionCategory


class TestTransactionCategory:
    """Test TransactionCategory model."""

    def test_valid_transaction_category(self):
        """Should create valid TransactionCategory objects with confidence."""
        category = TransactionCategory(transaction_id="txn_123", category="dining", confidence=0.85)
        assert category.transaction_id == "txn_123"
        assert category.category == "dining"
        assert category.confidence == 0.85

    def test_confidence_validation(self):
        """Should validate confidence is between 0 and 1."""
        # Valid confidence values
        category = TransactionCategory(transaction_id="txn_123", category="dining", confidence=0)
        assert category.confidence == 0

        category = TransactionCategory(transaction_id="txn_123", category="dining", confidence=1)
        assert category.confidence == 1

        category = TransactionCategory(transaction_id="txn_123", category="dining", confidence=0.5)
        assert category.confidence == 0.5

        # Invalid confidence values
        with pytest.raises(ValidationError):
            TransactionCategory(transaction_id="txn_123", category="dining", confidence=-0.1)

        with pytest.raises(ValidationError):
            TransactionCategory(transaction_id="txn_123", category="dining", confidence=1.01)

    def test_missing_fields(self):
        """Should raise ValidationError for missing required fields."""
        with pytest.raises(ValidationError):
            TransactionCategory(transaction_id="txn_123", category="dining")  # missing confidence

        with pytest.raises(ValidationError):
            TransactionCategory(transaction_id="txn_123", confidence=0.85)  # missing category

        with pytest.raises(ValidationError):
            TransactionCategory(category="dining", confidence=0.85)  # missing transaction_id


class TestClaudeContentBlock:
    """Test ClaudeContentBlock with automatic JSON parsing."""
    
    def test_well_formed_json_string(self):
        """Should handle well-formed JSON string from Claude."""
        json_text = '[{"transaction_id": "txn_123", "category": "dining"}, {"transaction_id": "txn_456", "category": "groceries"}]'
        
        block = ClaudeContentBlock(type="text", text=json_text)
        
        assert block.text == json_text
    
    def test_empty_array_string(self):
        """Should handle empty array string correctly."""
        block = ClaudeContentBlock(type="text", text="[]")
        assert block.text == "[]"
    
    def test_single_item_string(self):
        """Should handle single item string."""
        json_text = '[{"transaction_id": "txn_789", "category": "transport"}]'
        
        block = ClaudeContentBlock(type="text", text=json_text)
        
        assert block.text == json_text
    
    def test_any_string_content(self):
        """Should accept any string content."""
        # Invalid JSON should be accepted (parsing happens later in categorizer)
        block = ClaudeContentBlock(type="text", text='{"invalid": "json"')
        assert block.text == '{"invalid": "json"'
        
        # Valid JSON with extra fields should be accepted
        block = ClaudeContentBlock(type="text", text='[{"transaction_id": "txn_123", "category": "dining", "extra_field": "ignored"}]')
        assert "extra_field" in block.text
    
    def test_wrong_data_type(self):
        """Should raise ValidationError for non-string data types."""
        with pytest.raises(ValidationError):
            ClaudeContentBlock(type="text", text=123)
        
        with pytest.raises(ValidationError):
            ClaudeContentBlock(type="text", text=["not", "a", "string"])


class TestClaudeResponse:
    """Test full ClaudeResponse model."""
    
    def test_complete_well_formed_response(self):
        """Should parse a complete, well-formed Claude API response."""
        response_data = {
            "id": "msg_123",
            "type": "message",
            "role": "assistant",
            "content": [{
                "type": "text",
                "text": '[{"transaction_id": "txn_abc", "category": "dining"}, {"transaction_id": "txn_def", "category": "groceries"}]'
            }],
            "model": "claude-3-haiku-20240307",
            "stop_reason": "end_turn",
            "usage": {
                "input_tokens": 50,
                "output_tokens": 25
            }
        }
        
        response = ClaudeResponse(**response_data)
        
        assert response.id == "msg_123"
        assert response.role == "assistant"
        assert response.text == '[{"transaction_id": "txn_abc", "category": "dining"}, {"transaction_id": "txn_def", "category": "groceries"}]'
    
    def test_empty_content_list(self):
        """Should handle empty content list gracefully."""
        response_data = {
            "id": "msg_456",
            "type": "message", 
            "role": "assistant",
            "content": [],
            "model": "claude-3-haiku-20240307",
            "usage": {}
        }
        
        response = ClaudeResponse(**response_data)
        assert response.text == ""
    
    def test_empty_transactions_in_content(self):
        """Should handle empty transactions list in content."""
        response_data = {
            "id": "msg_789",
            "type": "message",
            "role": "assistant", 
            "content": [{
                "type": "text",
                "text": "[]"
            }],
            "model": "claude-3-haiku-20240307",
            "usage": {}
        }
        
        response = ClaudeResponse(**response_data)
        assert response.text == "[]"
    
    def test_malformed_usage_field(self):
        """Should handle different usage field formats."""
        # Usage as dict (current format)
        response_data = {
            "id": "msg_usage1",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "[]"}],
            "model": "claude-3-haiku-20240307",
            "usage": {"input_tokens": 10, "output_tokens": 5}
        }
        
        response = ClaudeResponse(**response_data)
        assert response.usage["input_tokens"] == 10
        
        # Empty usage dict
        response_data["usage"] = {}
        response = ClaudeResponse(**response_data)
        assert response.usage == {}
    
    def test_missing_optional_fields(self):
        """Should handle missing optional fields."""
        response_data = {
            "id": "msg_minimal",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "[]"}],
            "model": "claude-3-haiku-20240307",
            "usage": {}
            # stop_reason and stop_sequence are optional
        }
        
        response = ClaudeResponse(**response_data)
        assert response.stop_reason is None
        assert response.stop_sequence is None
    
    def test_invalid_transaction_in_response(self):
        """Should raise ValidationError for invalid transactions in response."""
        response_data = {
            "id": "msg_invalid",
            "type": "message",
            "role": "assistant",
            "content": [{
                "type": "text",
                "text": '[{"transaction_id": "txn_good", "category": "dining"}, {"transaction_id": "txn_bad"}]'  # missing category in second item
            }],
            "model": "claude-3-haiku-20240307",
            "usage": {}
        }
        
        # This should not raise ValidationError since we just store the string
        # The validation happens later in the categorizer when parsing
        response = ClaudeResponse(**response_data)
        assert "txn_bad" in response.text


class TestRealWorldScenarios:
    """Test scenarios that could happen in production."""
    
    def test_claude_returns_extra_fields(self):
        """Should handle when Claude returns extra fields we don't expect."""
        response_data = {
            "id": "msg_extra",
            "type": "message",
            "role": "assistant",
            "content": [{
                "type": "text", 
                "text": '[{"transaction_id": "txn_123", "category": "dining", "confidence": 0.95, "reasoning": "Restaurant transaction"}]'
            }],
            "model": "claude-3-haiku-20240307",
            "usage": {}
        }
        
        response = ClaudeResponse(**response_data)
        
        # Should still work, we just store the JSON string
        assert "txn_123" in response.text
        assert "dining" in response.text
        assert "confidence" in response.text
    
    def test_api_structure_changes(self):
        """Should fail gracefully if Claude API structure changes significantly."""
        # Content block with unexpected structure
        with pytest.raises(ValidationError):
            ClaudeResponse(**{
                "id": "msg_changed",
                "type": "message", 
                "role": "assistant",
                "content": [{
                    "type": "text",
                    "data": [{"transaction_id": "txn_123", "category": "dining"}]  # 'data' instead of 'text'
                }],
                "model": "claude-3-haiku-20240307",
                "usage": {}
            })
        
        # Missing required fields
        with pytest.raises(ValidationError):
            ClaudeResponse(**{
                "id": "msg_incomplete",
                "role": "assistant",
                # missing type, content, model, usage
            })
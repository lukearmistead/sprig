"""Tests for Claude API response models with real payloads."""


from sprig.models.claude import ClaudeResponse


class TestClaudeResponseRealFormat:
    """Test Claude response parsing with actual API payload format."""
    
    def test_actual_claude_api_response_format(self):
        """Test with the actual Claude API response format containing JSON string."""
        # This is the real format Claude returns based on our categorizer prompt
        response_data = {
            "id": "msg_01ABC123", 
            "type": "message",
            "role": "assistant",
            "content": [{
                "type": "text",
                "text": '[{"transaction_id": "txn_123", "category": "dining"}, {"transaction_id": "txn_456", "category": "groceries"}]'
            }],
            "model": "claude-3-haiku-20240307",
            "stop_reason": "end_turn",
            "usage": {
                "input_tokens": 150,
                "output_tokens": 45
            }
        }
        
        # This should parse successfully
        response = ClaudeResponse(**response_data)
        
        assert response.id == "msg_01ABC123"
        assert response.role == "assistant"
        
        # The text should be accessible as the JSON string
        json_text = response.text
        assert json_text == '[{"transaction_id": "txn_123", "category": "dining"}, {"transaction_id": "txn_456", "category": "groceries"}]'
    
    def test_claude_response_empty_array(self):
        """Test Claude response with empty categorization array."""
        response_data = {
            "id": "msg_02DEF456",
            "type": "message", 
            "role": "assistant",
            "content": [{
                "type": "text",
                "text": "[]"
            }],
            "model": "claude-3-haiku-20240307",
            "stop_reason": "end_turn",
            "usage": {}
        }
        
        response = ClaudeResponse(**response_data)
        assert response.text == "[]"
    
    def test_claude_response_single_transaction(self):
        """Test Claude response with single transaction categorization."""
        response_data = {
            "id": "msg_03GHI789",
            "type": "message",
            "role": "assistant", 
            "content": [{
                "type": "text",
                "text": '[{"transaction_id": "txn_789", "category": "transport"}]'
            }],
            "model": "claude-3-haiku-20240307",
            "usage": {}
        }
        
        response = ClaudeResponse(**response_data)
        assert response.text == '[{"transaction_id": "txn_789", "category": "transport"}]'
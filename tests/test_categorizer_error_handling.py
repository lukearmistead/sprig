"""Tests for improved error handling in transaction categorization."""

from datetime import date
from unittest.mock import Mock, patch, call

from sprig.categorizer import ClaudeCategorizer
from sprig.models import RuntimeConfig, TellerTransaction


class TestErrorHandling:
    """Test that errors are properly reported, not silently swallowed."""
    
    def setup_method(self):
        """Set up test categorizer instance."""
        self.runtime_config = Mock(spec=RuntimeConfig)
        self.runtime_config.claude_api_key = "test_key"
        
        self.test_transactions = [
            TellerTransaction(
                id="txn_1",
                account_id="acc_1",
                amount=25.50,
                description="Restaurant ABC",
                date=date(2024, 1, 1),
                type="debit",
                status="posted"
            ),
            TellerTransaction(
                id="txn_2",
                account_id="acc_1", 
                amount=50.00,
                description="Gas Station XYZ",
                date=date(2024, 1, 2),
                type="debit",
                status="posted"
            )
        ]
    
    @patch('anthropic.Anthropic')
    @patch('sprig.categorizer.logger')
    def test_api_error_is_reported(self, mock_logger, mock_anthropic):
        """Test that API errors are logged, not silently ignored."""
        mock_client = Mock()
        mock_anthropic.return_value = mock_client
        
        # Simulate API error
        mock_client.messages.create.side_effect = Exception("API rate limit exceeded")
        
        categorizer = ClaudeCategorizer(self.runtime_config)
        account_info = {}  # Empty account info for test
        result = categorizer.categorize_batch(self.test_transactions, account_info)
        
        # Should log the error
        error_logged = any("API rate limit exceeded" in str(call) for call in mock_logger.error.call_args_list)
        assert error_logged, "API error should be logged"
        
        # Should return empty dict when batch fails
        assert result == {}
    
    @patch('anthropic.Anthropic')
    @patch('sprig.categorizer.logger')
    def test_json_parsing_error_is_reported(self, mock_logger, mock_anthropic):
        """Test that JSON parsing errors are reported."""
        mock_client = Mock()
        mock_anthropic.return_value = mock_client
        
        # Return invalid JSON
        mock_api_response = Mock()
        mock_api_response.model_dump.return_value = {
            "id": "msg_123",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "not valid json"}],
            "model": "claude-haiku-4-5-20251001",
            "usage": {}
        }
        mock_client.messages.create.return_value = mock_api_response
        
        categorizer = ClaudeCategorizer(self.runtime_config)
        account_info = {}  # Empty account info for test
        result = categorizer.categorize_batch(self.test_transactions, account_info)
        
        # Should log parsing error
        error_logged = any("Failed to parse" in str(call) or "Invalid JSON" in str(call) 
                          for call in mock_logger.error.call_args_list)
        assert error_logged, "JSON parsing error should be logged"
        
        # Should return empty dict for failed batch
        assert result == {}


class TestRetryLogic:
    """Test that failed batches are retried with exponential backoff."""
    
    def setup_method(self):
        """Set up test categorizer instance."""
        self.runtime_config = Mock(spec=RuntimeConfig)
        self.runtime_config.claude_api_key = "test_key"
        
        self.test_transactions = [
            TellerTransaction(
                id="txn_1",
                account_id="acc_1",
                amount=25.50,
                description="Restaurant",
                date=date(2024, 1, 1),
                type="debit",
                status="posted"
            )
        ]
    
    @patch('anthropic.Anthropic')
    @patch('time.sleep')
    @patch('sprig.categorizer.logger')
    def test_retry_on_failure(self, mock_logger, mock_sleep, mock_anthropic):
        """Test that failed API calls are retried up to 3 times."""
        mock_client = Mock()
        mock_anthropic.return_value = mock_client
        
        # Fail twice, then succeed
        mock_api_response = Mock()
        mock_api_response.model_dump.return_value = {
            "id": "msg_123",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": '{"transaction_id": "txn_1", "category": "dining"}]'}],
            "model": "claude-haiku-4-5-20251001",
            "usage": {}
        }
        
        mock_client.messages.create.side_effect = [
            Exception("Network error"),
            Exception("Timeout"),
            mock_api_response
        ]
        
        categorizer = ClaudeCategorizer(self.runtime_config)
        account_info = {}  # Empty account info for test
        result = categorizer.categorize_batch(self.test_transactions, account_info)
        
        # Should retry 3 times
        assert mock_client.messages.create.call_count == 3
        
        # Should use exponential backoff (1s, 2s between retries)
        assert mock_sleep.call_count == 2
        mock_sleep.assert_has_calls([call(1), call(2)])
        
        # Should eventually return the successful result
        assert result == {"txn_1": "dining"}
        
        # Should log retry attempts
        retry_logged = any("Retrying" in str(call) for call in mock_logger.info.call_args_list)
        assert retry_logged, "Retry attempts should be logged"
    
    @patch('anthropic.Anthropic')
    @patch('time.sleep')
    @patch('sprig.categorizer.logger')
    def test_give_up_after_max_retries(self, mock_logger, mock_sleep, mock_anthropic):
        """Test that categorizer gives up after 3 failed attempts."""
        mock_client = Mock()
        mock_anthropic.return_value = mock_client
        
        # Always fail
        mock_client.messages.create.side_effect = Exception("Persistent error")
        
        categorizer = ClaudeCategorizer(self.runtime_config)
        account_info = {}  # Empty account info for test
        result = categorizer.categorize_batch(self.test_transactions, account_info)
        
        # Should try exactly 3 times
        assert mock_client.messages.create.call_count == 3
        
        # Should return empty dict after giving up
        assert result == {}
        
        # Should log that it gave up
        gave_up_logged = any("Failed after" in str(call) or "attempts" in str(call) 
                            for call in mock_logger.error.call_args_list)
        assert gave_up_logged, "Should log when giving up after max retries"


class TestProgressTracking:
    """Test that progress is reported during categorization."""
    
    @patch('sprig.categorizer.ClaudeCategorizer.categorize_batch')
    @patch('sprig.database.SprigDatabase')
    @patch('sprig.sync.logger')
    def test_batch_progress_is_shown(self, mock_logger, mock_db, mock_categorize_batch):
        """Test that progress is shown for each batch."""
        from sprig.sync import categorize_uncategorized_transactions
        
        # Mock database returning 50 uncategorized transactions
        mock_db_instance = Mock()
        mock_db.return_value = mock_db_instance
        
        # Create 50 mock transaction rows (including account columns and counterparty)
        mock_transactions = [(f"txn_{i}", f"Description {i}", 10.0, "2024-01-01", "debit", 
                             f"acc_{i}", f"Account {i}", "checking", f"Merchant {i}") 
                            for i in range(50)]
        mock_db_instance.get_uncategorized_transactions.return_value = mock_transactions
        
        # Mock successful categorization
        mock_categorize_batch.return_value = {f"txn_{i}": "dining" for i in range(20)}
        
        runtime_config = Mock()
        runtime_config.claude_api_key = "test_key"
        
        categorize_uncategorized_transactions(runtime_config, mock_db_instance)
        
        # Should show batch progress (50 transactions = 3 batches with batch size 20)
        progress_logged = any(
            "batch 1 of 3" in str(call).lower() or 
            "processing batch" in str(call).lower()
            for call in mock_logger.debug.call_args_list
        )
        assert progress_logged, "Should show batch progress"
    
    @patch('sprig.categorizer.ClaudeCategorizer.categorize_batch')
    @patch('sprig.database.SprigDatabase')
    @patch('sprig.sync.logger')
    def test_summary_shows_results(self, mock_logger, mock_db, mock_categorize_batch):
        """Test that a summary is shown at the end."""
        from sprig.sync import categorize_uncategorized_transactions
        
        mock_db_instance = Mock()
        mock_db.return_value = mock_db_instance
        
        # Create 30 transactions (2 batches) with account columns and counterparty
        mock_transactions = [(f"txn_{i}", f"Description {i}", 10.0, "2024-01-01", "debit",
                             f"acc_{i}", f"Account {i}", "checking", f"Merchant {i}") 
                            for i in range(30)]
        mock_db_instance.get_uncategorized_transactions.return_value = mock_transactions
        
        # First batch succeeds, second batch fails
        mock_categorize_batch.side_effect = [
            {f"txn_{i}": "dining" for i in range(20)},  # First batch succeeds
            {}  # Second batch fails
        ]
        
        runtime_config = Mock()
        runtime_config.claude_api_key = "test_key"
        
        categorize_uncategorized_transactions(runtime_config, mock_db_instance)
        
        # Should show summary with success/failure counts
        summary_logged = any(
            ("categorized: 20" in str(call).lower() or 
             "failed: 10" in str(call).lower())
            for call in mock_logger.info.call_args_list + mock_logger.warning.call_args_list
        )
        assert summary_logged, "Should show categorization summary"
"""Tests for transaction categorization functionality."""

from unittest.mock import Mock, patch

from sprig.categorize import categorize_inferentially
from sprig.models import TransactionCategory
from sprig.models.config import Config
from sprig.models.claude import TransactionView



class TestBuildCategorizationPrompt:
    """Test prompt building functionality."""

    def test_build_prompt_includes_descriptions(self):
        """Test that prompt includes category descriptions."""

        transaction_views = [
            TransactionView(
                id="txn_123",
                date="2024-01-01",
                description="Restaurant",
                amount=25.50,
                inferred_category=None,
                confidence=None,
                counterparty=None,
                account_name="Checking",
                account_subtype="checking",
                account_last_four="1234",
            )
        ]

        # Load actual category config
        category_config = Config.load()

        # Mock Agent to inspect the prompt
        with patch('sprig.categorize.AnthropicProvider'), patch('sprig.categorize.Agent') as MockAgent:
            mock_agent_instance = Mock()
            mock_agent_instance.run_sync.return_value = Mock(output=[])
            MockAgent.return_value = mock_agent_instance

            # Call categorize_inferentially which should build the prompt internally
            categorize_inferentially(transaction_views, category_config)

            # Get the prompt from the call args
            call_args = mock_agent_instance.run_sync.call_args
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
        self.category_config = Config.load()

    def test_validate_categories_valid_response(self):
        """Test validating valid response from agent."""
        transaction_views = [
            TransactionView(
                id="txn_123",
                date="2024-01-01",
                description="Restaurant",
                amount=25.50,
                inferred_category=None,
                confidence=None,
                counterparty=None,
                account_name="Checking",
                account_subtype="checking",
                account_last_four=None,
            ),
            TransactionView(
                id="txn_456",
                date="2024-01-02",
                description="Grocery Store",
                amount=50.00,
                inferred_category=None,
                confidence=None,
                counterparty=None,
                account_name="Checking",
                account_subtype="checking",
                account_last_four=None,
            )
        ]

        # Mock agent to return valid categories
        with patch('sprig.categorize.AnthropicProvider'), patch('sprig.categorize.Agent') as MockAgent:
            mock_agent = Mock()
            MockAgent.return_value = mock_agent
            mock_result = Mock()
            mock_result.output = [
                TransactionCategory(transaction_id="txn_123", category="dining", confidence=0.9),
                TransactionCategory(transaction_id="txn_456", category="groceries", confidence=0.85)
            ]
            mock_agent.run_sync.return_value = mock_result

            result = categorize_inferentially(transaction_views, self.category_config)

            assert len(result) == 2
            assert result[0].transaction_id == "txn_123"
            assert result[0].category == "dining"
            assert result[1].transaction_id == "txn_456"
            assert result[1].category == "groceries"

    def test_validate_categories_invalid_category(self):
        """Test that invalid categories are filtered out."""
        transaction_views = [
            TransactionView(
                id="txn_123",
                date="2024-01-01",
                description="Restaurant",
                amount=25.50,
                inferred_category=None,
                confidence=None,
                counterparty=None,
                account_name=None,
                account_subtype=None,
                account_last_four=None,
            ),
            TransactionView(
                id="txn_456",
                date="2024-01-02",
                description="Unknown",
                amount=50.00,
                inferred_category=None,
                confidence=None,
                counterparty=None,
                account_name=None,
                account_subtype=None,
                account_last_four=None,
            )
        ]

        # Mock agent to return mix of valid and invalid categories
        with patch('sprig.categorize.AnthropicProvider'), patch('sprig.categorize.Agent') as MockAgent:
            mock_agent = Mock()
            MockAgent.return_value = mock_agent
            mock_result = Mock()
            mock_result.output = [
                TransactionCategory(transaction_id="txn_123", category="dining", confidence=0.9),
                TransactionCategory(transaction_id="txn_456", category="invalid_category", confidence=0.5)
            ]
            mock_agent.run_sync.return_value = mock_result

            result = categorize_inferentially(transaction_views, self.category_config)

            # Invalid category should be filtered out
            assert len(result) == 1
            assert result[0].transaction_id == "txn_123"
            assert result[0].category == "dining"

    def test_validate_categories_mixed_valid_invalid(self):
        """Test mix of valid and invalid categories."""
        transaction_views = [
            TransactionView(
                id="txn_1",
                date="2024-01-01",
                description="Restaurant",
                amount=25.50,
                inferred_category=None,
                confidence=None,
                counterparty=None,
                account_name=None,
                account_subtype=None,
                account_last_four=None,
            ),
            TransactionView(
                id="txn_2",
                date="2024-01-02",
                description="Unknown",
                amount=30.00,
                inferred_category=None,
                confidence=None,
                counterparty=None,
                account_name=None,
                account_subtype=None,
                account_last_four=None,
            ),
            TransactionView(
                id="txn_3",
                date="2024-01-03",
                description="Gas Station",
                amount=45.00,
                inferred_category=None,
                confidence=None,
                counterparty=None,
                account_name=None,
                account_subtype=None,
                account_last_four=None,
            )
        ]

        # Mock agent to return mix of valid and invalid
        with patch('sprig.categorize.AnthropicProvider'), patch('sprig.categorize.Agent') as MockAgent:
            mock_agent = Mock()
            MockAgent.return_value = mock_agent
            mock_result = Mock()
            mock_result.output = [
                TransactionCategory(transaction_id="txn_1", category="dining", confidence=0.9),
                TransactionCategory(transaction_id="txn_2", category="wrong", confidence=0.5),
                TransactionCategory(transaction_id="txn_3", category="transport", confidence=0.85)
            ]
            mock_agent.run_sync.return_value = mock_result

            result = categorize_inferentially(transaction_views, self.category_config)

            # Only valid categories should be returned
            assert len(result) == 2
            assert result[0].transaction_id == "txn_1"
            assert result[0].category == "dining"
            assert result[1].transaction_id == "txn_3"
            assert result[1].category == "transport"


    def test_validate_categories_empty_list(self):
        """Test handling empty list."""
        transaction_views = []

        # Mock agent to return empty list
        with patch('sprig.categorize.AnthropicProvider'), patch('sprig.categorize.Agent') as MockAgent:
            mock_agent = Mock()
            MockAgent.return_value = mock_agent
            mock_result = Mock()
            mock_result.output = []
            mock_agent.run_sync.return_value = mock_result

            result = categorize_inferentially(transaction_views, self.category_config)

            assert result == []

    def test_validate_categories_all_invalid(self):
        """Test when all categories are invalid."""
        transaction_views = [
            TransactionView(
                id="txn_1",
                date="2024-01-01",
                description="Unknown 1",
                amount=25.50,
                inferred_category=None,
                confidence=None,
                counterparty=None,
                account_name=None,
                account_subtype=None,
                account_last_four=None,
            ),
            TransactionView(
                id="txn_2",
                date="2024-01-02",
                description="Unknown 2",
                amount=30.00,
                inferred_category=None,
                confidence=None,
                counterparty=None,
                account_name=None,
                account_subtype=None,
                account_last_four=None,
            )
        ]

        # Mock agent to return all invalid categories
        with patch('sprig.categorize.AnthropicProvider'), patch('sprig.categorize.Agent') as MockAgent:
            mock_agent = Mock()
            MockAgent.return_value = mock_agent
            mock_result = Mock()
            mock_result.output = [
                TransactionCategory(transaction_id="txn_1", category="fake1", confidence=0.5),
                TransactionCategory(transaction_id="txn_2", category="fake2", confidence=0.5)
            ]
            mock_agent.run_sync.return_value = mock_result

            result = categorize_inferentially(transaction_views, self.category_config)

            # All invalid, so empty list
            assert result == []




class TestCategorizeBatchIntegration:
    """Test full categorization workflow."""

    def test_categorize_batch_full_flow(self):
        """Test full categorization flow with mocked agent."""
        # Create test transaction views
        transaction_views = [
            TransactionView(
                id="txn_ABC123",
                date="2024-01-01",
                description="Restaurant",
                amount=25.50,
                inferred_category=None,
                confidence=None,
                counterparty=None,
                account_name="Checking",
                account_subtype="checking",
                account_last_four=None,
            ),
            TransactionView(
                id="txn_DEF456",
                date="2024-01-02",
                description="Gas Station",
                amount=45.00,
                inferred_category=None,
                confidence=None,
                counterparty=None,
                account_name="Checking",
                account_subtype="checking",
                account_last_four=None,
            ),
            TransactionView(
                id="txn_GHI789",
                date="2024-01-03",
                description="Supermarket",
                amount=85.30,
                inferred_category=None,
                confidence=None,
                counterparty=None,
                account_name="Checking",
                account_subtype="checking",
                account_last_four=None,
            )
        ]

        # Run categorization
        category_config = Config.load()

        # Mock categorization_agent.run_sync
        with patch('sprig.categorize.AnthropicProvider'), patch('sprig.categorize.Agent') as MockAgent:
            mock_agent = Mock()
            MockAgent.return_value = mock_agent
            mock_result = Mock()
            mock_result.output = [
                TransactionCategory(transaction_id="txn_ABC123", category="dining", confidence=0.9),
                TransactionCategory(transaction_id="txn_DEF456", category="transport", confidence=0.85),
                TransactionCategory(transaction_id="txn_GHI789", category="groceries", confidence=0.95)
            ]
            mock_agent.run_sync.return_value = mock_result

            result = categorize_inferentially(transaction_views, category_config)

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
        # Create test transaction views
        transaction_views = [
            TransactionView(
                id="txn_1",
                date="2024-01-01",
                description="Restaurant",
                amount=25.50,
                inferred_category=None,
                confidence=None,
                counterparty=None,
                account_name=None,
                account_subtype=None,
                account_last_four=None,
            )
        ]

        # Run categorization
        category_config = Config.load()

        # Mock agent to return mix of valid and invalid
        with patch('sprig.categorize.AnthropicProvider'), patch('sprig.categorize.Agent') as MockAgent:
            mock_agent = Mock()
            MockAgent.return_value = mock_agent
            mock_result = Mock()
            mock_result.output = [
                TransactionCategory(transaction_id="txn_1", category="dining", confidence=0.9),
                TransactionCategory(transaction_id="txn_2", category="invalid_cat", confidence=0.5),
                TransactionCategory(transaction_id="txn_3", category="groceries", confidence=0.85)
            ]
            mock_agent.run_sync.return_value = mock_result

            result = categorize_inferentially(transaction_views, category_config)

            # Assert invalid category is filtered out
            assert len(result) == 2
            assert result[0].transaction_id == "txn_1"
            assert result[0].category == "dining"
            assert result[1].transaction_id == "txn_3"
            assert result[1].category == "groceries"

    def test_categorize_with_account_info_context(self):
        """Test that account context from TransactionView is used for categorization."""
        transaction_views = [
            TransactionView(
                id="txn_cc",
                date="2024-01-01",
                description="Payment received",
                amount=-50.00,  # Negative on credit card (payment/refund)
                inferred_category=None,
                confidence=None,
                counterparty="ACH Transfer",
                account_name="Chase Sapphire",
                account_subtype="credit_card",
                account_last_four="4567",
            )
        ]

        category_config = Config.load()

        with patch('sprig.categorize.AnthropicProvider'), patch('sprig.categorize.Agent') as MockAgent:
            mock_agent = Mock()
            MockAgent.return_value = mock_agent
            mock_result = Mock()
            mock_result.output = [
                TransactionCategory(transaction_id="txn_cc", category="transfers", confidence=0.95)
            ]
            mock_agent.run_sync.return_value = mock_result

            result = categorize_inferentially(transaction_views, category_config)

            # Verify agent was called
            mock_agent.run_sync.assert_called_once()
            call_args = str(mock_agent.run_sync.call_args)

            # Verify account context was included in the call
            assert "credit_card" in call_args or "Chase Sapphire" in call_args

            # Verify categorization result
            assert len(result) == 1
            assert result[0].category == "transfers"


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def setup_method(self):
        """Set up test category config."""
        self.category_config = Config.load()

    def test_response_with_numeric_transaction_ids(self):
        """Test transaction IDs that are numeric strings."""
        transaction_views = [
            TransactionView(
                id="12345",
                date="2024-01-01",
                description="Restaurant",
                amount=25.50,
                inferred_category=None,
                confidence=None,
                counterparty=None,
                account_name=None,
                account_subtype=None,
                account_last_four=None,
            ),
            TransactionView(
                id="67890",
                date="2024-01-02",
                description="Gas Station",
                amount=45.00,
                inferred_category=None,
                confidence=None,
                counterparty=None,
                account_name=None,
                account_subtype=None,
                account_last_four=None,
            )
        ]

        with patch('sprig.categorize.AnthropicProvider'), patch('sprig.categorize.Agent') as MockAgent:
            mock_agent = Mock()
            MockAgent.return_value = mock_agent
            mock_result = Mock()
            mock_result.output = [
                TransactionCategory(transaction_id="12345", category="dining", confidence=0.9),
                TransactionCategory(transaction_id="67890", category="transport", confidence=0.85)
            ]
            mock_agent.run_sync.return_value = mock_result

            result = categorize_inferentially(transaction_views, self.category_config)

            assert len(result) == 2
            assert result[0].transaction_id == "12345"
            assert result[0].category == "dining"
            assert result[1].transaction_id == "67890"
            assert result[1].category == "transport"

    def test_response_with_special_characters(self):
        """Test transaction IDs with special characters."""
        transaction_views = [
            TransactionView(
                id="txn_abc-123",
                date="2024-01-01",
                description="Restaurant",
                amount=25.50,
                inferred_category=None,
                confidence=None,
                counterparty=None,
                account_name=None,
                account_subtype=None,
                account_last_four=None,
            ),
            TransactionView(
                id="txn_def_456",
                date="2024-01-02",
                description="Gas Station",
                amount=45.00,
                inferred_category=None,
                confidence=None,
                counterparty=None,
                account_name=None,
                account_subtype=None,
                account_last_four=None,
            )
        ]

        with patch('sprig.categorize.AnthropicProvider'), patch('sprig.categorize.Agent') as MockAgent:
            mock_agent = Mock()
            MockAgent.return_value = mock_agent
            mock_result = Mock()
            mock_result.output = [
                TransactionCategory(transaction_id="txn_abc-123", category="dining", confidence=0.9),
                TransactionCategory(transaction_id="txn_def_456", category="transport", confidence=0.85)
            ]
            mock_agent.run_sync.return_value = mock_result

            result = categorize_inferentially(transaction_views, self.category_config)

            assert len(result) == 2
            assert result[0].transaction_id == "txn_abc-123"
            assert result[0].category == "dining"
            assert result[1].transaction_id == "txn_def_456"
            assert result[1].category == "transport"

    def test_category_config_loads(self):
        """Test that category config loads properly."""
        category_config = Config.load()
        category_names = {cat.name for cat in category_config.categories}
        assert "undefined" in category_names  # undefined should still be a valid category


class TestCategorizeBatchProcessing:
    """Test batch processing with categorize_in_batches function."""

    def test_categorize_in_batches_splits_into_batches(self):
        """Test that categorize_in_batches splits transactions into correct batch sizes."""
        from sprig.categorize import categorize_in_batches

        # Create 25 transaction views to test batching
        transaction_views = [
            TransactionView(
                id=f"txn_{i}",
                date="2024-01-15",
                description=f"Transaction {i}",
                amount=-10.00,
                inferred_category=None,
                confidence=None,
                counterparty=None,
                account_name="Checking",
                account_subtype="checking",
                account_last_four="1234",
            )
            for i in range(25)
        ]

        category_config = Config.load()
        category_config.batch_size = 10

        call_count = 0
        batch_sizes = []

        with patch('sprig.categorize.categorize_inferentially') as mock_categorize:
            def track_calls(views, config):
                nonlocal call_count
                call_count += 1
                batch_sizes.append(len(views))
                # Return mock results for the batch
                return [
                    TransactionCategory(transaction_id=v.id, category="general", confidence=0.8)
                    for v in views
                ]

            mock_categorize.side_effect = track_calls

            results = categorize_in_batches(transaction_views, category_config)

            # Should make 3 calls: 10, 10, 5
            assert call_count == 3
            assert batch_sizes == [10, 10, 5]
            assert len(results) == 25

    def test_categorize_in_batches_returns_all_results(self):
        """Test that categorize_in_batches returns combined results from all batches."""
        from sprig.categorize import categorize_in_batches

        transaction_views = [
            TransactionView(
                id=f"txn_{i}",
                date="2024-01-15",
                description=f"Transaction {i}",
                amount=-10.00,
                inferred_category=None,
                confidence=None,
                counterparty=None,
                account_name="Checking",
                account_subtype="checking",
                account_last_four="1234",
            )
            for i in range(20)
        ]

        category_config = Config.load()

        with patch('sprig.categorize.categorize_inferentially') as mock_categorize:
            def mock_categorize_func(views, config):
                # Return results for each transaction in the batch
                return [
                    TransactionCategory(transaction_id=v.id, category="general", confidence=0.8)
                    for v in views
                ]

            mock_categorize.side_effect = mock_categorize_func

            results = categorize_in_batches(transaction_views, category_config)

            # Should return all 20 results
            assert len(results) == 20
            result_ids = {r.transaction_id for r in results}
            expected_ids = {f"txn_{i}" for i in range(20)}
            assert result_ids == expected_ids


class TestCategorizationWithTransactionView:
    """Test categorization using TransactionView directly (no TellerTransaction conversion)."""

    def test_categorize_inferentially_accepts_transaction_views(self):
        """Test that categorize_inferentially accepts TransactionView list directly."""
        from sprig.models.claude import TransactionView

        # Create TransactionView objects directly (as they'd come from database)
        transaction_views = [
            TransactionView(
                id="txn_123",
                date="2024-01-15",
                description="STARBUCKS",
                amount=-5.75,
                inferred_category=None,
                confidence=None,
                counterparty="Starbucks",
                account_name="Chase Sapphire",
                account_subtype="credit_card",
                account_last_four="4242",
            ),
            TransactionView(
                id="txn_456",
                date="2024-01-16",
                description="WHOLE FOODS",
                amount=-87.23,
                inferred_category=None,
                confidence=None,
                counterparty="Whole Foods Market",
                account_name="Chase Sapphire",
                account_subtype="credit_card",
                account_last_four="4242",
            ),
        ]

        category_config = Config.load()

        # Mock agent response
        with patch('sprig.categorize.AnthropicProvider'), patch('sprig.categorize.Agent') as MockAgent:
            mock_agent = Mock()
            MockAgent.return_value = mock_agent
            mock_result = Mock()
            mock_result.output = [
                TransactionCategory(transaction_id="txn_123", category="dining", confidence=0.95),
                TransactionCategory(transaction_id="txn_456", category="groceries", confidence=0.9)
            ]
            mock_agent.run_sync.return_value = mock_result

            # Call with TransactionView list - NO account_info parameter
            result = categorize_inferentially(transaction_views, category_config)

            # Verify results
            assert len(result) == 2
            assert result[0].transaction_id == "txn_123"
            assert result[0].category == "dining"
            assert result[1].transaction_id == "txn_456"
            assert result[1].category == "groceries"

    def test_categorize_inferentially_includes_account_context_from_view(self):
        """Test that account context from TransactionView is included in prompt."""
        from sprig.models.claude import TransactionView

        transaction_views = [
            TransactionView(
                id="txn_cc",
                date="2024-01-20",
                description="PAYMENT RECEIVED",
                amount=-150.00,
                inferred_category=None,
                confidence=None,
                counterparty="ACH Transfer",
                account_name="Chase Sapphire Reserve",
                account_subtype="credit_card",
                account_last_four="9876",
            ),
        ]

        category_config = Config.load()

        with patch('sprig.categorize.AnthropicProvider'), patch('sprig.categorize.Agent') as MockAgent:
            mock_agent = Mock()
            MockAgent.return_value = mock_agent
            mock_result = Mock()
            mock_result.output = [
                TransactionCategory(transaction_id="txn_cc", category="transfers", confidence=0.9)
            ]
            mock_agent.run_sync.return_value = mock_result

            result = categorize_inferentially(transaction_views, category_config)

            # Verify agent was called with context
            mock_agent.run_sync.assert_called_once()
            call_args = str(mock_agent.run_sync.call_args)

            # Account context should appear in the prompt
            assert "credit_card" in call_args or "Chase Sapphire Reserve" in call_args

            # Verify result
            assert len(result) == 1
            assert result[0].category == "transfers"

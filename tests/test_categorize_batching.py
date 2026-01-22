
import unittest
from unittest.mock import patch
from datetime import date
from sprig.categorize import categorize_in_batches
from sprig.models.claude import TransactionView

class TestCategorizeBatching(unittest.TestCase):
    def setUp(self):
        self.transactions = [
            TransactionView(
                id=f"t{i}",
                date=str(date.today()),
                description=f"d{i}",
                amount=10.0,
                inferred_category=None,
                confidence=None,
                counterparty=None,
                account_name="Test Account",
                account_subtype="checking",
                account_last_four=None
            ) for i in range(5)
        ]
        from sprig.models.config import Config
        self.config = Config.load()

    @patch('sprig.categorize.categorize_inferentially')
    def test_categorize_in_batches_splits_into_correct_batch_sizes(self, mock_categorize):
        mock_categorize.return_value = []
        categorize_in_batches(self.transactions, self.config, batch_size=2)

        self.assertEqual(mock_categorize.call_count, 3)
        calls = mock_categorize.call_args_list
        self.assertEqual(len(calls[0][0][0]), 2)  # First batch: 2 transactions
        self.assertEqual(len(calls[1][0][0]), 2)  # Second batch: 2 transactions
        self.assertEqual(len(calls[2][0][0]), 1)  # Third batch: 1 transaction

if __name__ == '__main__':
    unittest.main()

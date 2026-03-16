"""Integration tests for the pipeline orchestrator."""

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from sprig.database import SprigDatabase
from sprig.fetch import fetch_token
from sprig.pipeline import run_pipeline


def test_fetch_and_persist():
    """Integration test: fetch yields data, pipeline persists it."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        db = SprigDatabase(db_path)

        mock_client = Mock()
        mock_client.get_accounts.return_value = [
            {
                "id": "acc_integration",
                "name": "Integration Test Account",
                "type": "depository",
                "currency": "USD",
                "status": "open",
            }
        ]
        mock_client.get_transactions.return_value = [
            {
                "id": "txn_integration",
                "account_id": "acc_integration",
                "amount": 100.00,
                "description": "Integration Test Transaction",
                "date": "2024-01-15",
                "type": "deposit",
                "status": "posted",
            }
        ]

        # Pipeline-style: consume generator, persist to DB
        for account, transactions in fetch_token(mock_client, "test_token"):
            db.save_account(account)
            db.sync_transactions(transactions)

        with sqlite3.connect(db_path) as conn:
            assert conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 1
            assert conn.execute(
                "SELECT name FROM accounts WHERE id = 'acc_integration'"
            ).fetchone()[0] == "Integration Test Account"


def test_pipeline_skips_categorization_when_no_claude_key():
    """Empty claude_key: fetch and export run, categorization is skipped."""
    config = Mock()
    config.claude_key = ""
    config.access_tokens = ["tok"]
    config.from_date = None
    config.cert_path = "certs/certificate.pem"
    config.key_path = "certs/private_key.pem"

    with patch("sprig.pipeline.get_default_db_path") as mock_db_path, \
         patch("sprig.pipeline.SprigDatabase"), \
         patch("sprig.pipeline.resolve_cert_path", side_effect=lambda p: p), \
         patch("sprig.pipeline.TellerClient"), \
         patch("sprig.pipeline.fetch_all", return_value=[]), \
         patch("sprig.pipeline.categorize_manually") as mock_manual, \
         patch("sprig.pipeline.categorize_in_batches") as mock_batches, \
         patch("sprig.pipeline.export_transactions_to_csv"):
        mock_db_path.return_value = Path("/tmp/test.db")
        run_pipeline(config)
        mock_manual.assert_not_called()
        mock_batches.assert_not_called()


def test_pipeline_runs_categorization_when_claude_key_present():
    """Non-empty claude_key: categorization steps run."""
    config = Mock()
    config.claude_key = "sk-test"
    config.access_tokens = ["tok"]
    config.from_date = None
    config.cert_path = "certs/certificate.pem"
    config.key_path = "certs/private_key.pem"

    with patch("sprig.pipeline.get_default_db_path") as mock_db_path, \
         patch("sprig.pipeline.SprigDatabase") as mock_db_cls, \
         patch("sprig.pipeline.resolve_cert_path", side_effect=lambda p: p), \
         patch("sprig.pipeline.TellerClient"), \
         patch("sprig.pipeline.fetch_all", return_value=[]), \
         patch("sprig.pipeline.categorize_manually", return_value=[]) as mock_manual, \
         patch("sprig.pipeline.categorize_in_batches") as mock_batches, \
         patch("sprig.pipeline.export_transactions_to_csv"):
        mock_db_path.return_value = Path("/tmp/test.db")
        mock_db_cls.return_value.get_uncategorized_transactions.return_value = []
        run_pipeline(config)
        mock_manual.assert_called_once()
        mock_batches.assert_not_called()  # No uncategorized transactions

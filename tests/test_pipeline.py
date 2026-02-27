"""Integration tests for the pipeline orchestrator."""

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import Mock

from sprig.database import SprigDatabase
from sprig.fetch import fetch_token


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
            for txn in transactions:
                db.sync_transaction(txn)

        with sqlite3.connect(db_path) as conn:
            assert conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 1
            assert conn.execute(
                "SELECT name FROM accounts WHERE id = 'acc_integration'"
            ).fetchone()[0] == "Integration Test Account"

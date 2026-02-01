"""Database operations for Sprig."""

import json
import sqlite3
from datetime import date
from pathlib import Path

import sprig.credentials as credentials
from sprig.models import TellerAccount, TellerTransaction


def get_db_path() -> Path:
    """Get resolved database path."""
    db_path = credentials.get_database_path()
    if db_path:
        path = Path(db_path.value)
        return path if path.is_absolute() else credentials.get_sprig_home() / db_path.value
    return credentials.get_default_db_path()


class SprigDatabase:
    """SQLite database for storing Teller data."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._initialize_database()

    def _initialize_database(self):
        """Create database tables if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    subtype TEXT,
                    institution TEXT,
                    enrollment_id TEXT,
                    currency TEXT NOT NULL,
                    status TEXT NOT NULL,
                    last_four TEXT,
                    links TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    amount REAL NOT NULL,
                    description TEXT NOT NULL,
                    date TEXT NOT NULL,
                    type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    details TEXT,
                    running_balance REAL,
                    links TEXT,
                    inferred_category TEXT,
                    confidence REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def _query(self, sql: str, params=None, as_row=False):
        """Execute a SELECT query and return all results."""
        with sqlite3.connect(self.db_path) as conn:
            if as_row:
                conn.row_factory = sqlite3.Row
            return conn.execute(sql, params or ()).fetchall()

    def _execute(self, sql: str, params=None):
        """Execute an INSERT/UPDATE/DELETE and commit."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(sql, params or ())
            conn.commit()

    def save_account(self, account: TellerAccount):
        """Insert or replace an account."""
        data = account.model_dump(mode='json')
        for key in ('links', 'institution'):
            if data.get(key) is not None:
                data[key] = json.dumps(data[key])
        columns = list(data.keys())
        placeholders = ", ".join(["?"] * len(columns))
        sql = f"INSERT OR REPLACE INTO accounts ({', '.join(columns)}) VALUES ({placeholders})"
        self._execute(sql, list(data.values()))

    def sync_transaction(self, transaction: TellerTransaction):
        """Upsert transaction, preserving any existing category."""
        data = transaction.model_dump(mode='json')
        for key in ('links', 'details'):
            if data.get(key) is not None:
                data[key] = json.dumps(data[key])

        # Fields that come from Teller (exclude our category fields)
        teller_fields = [k for k in data.keys() if k not in ("inferred_category", "confidence")]

        columns = ", ".join(teller_fields)
        placeholders = ", ".join(["?"] * len(teller_fields))
        updates = ", ".join(f"{k} = excluded.{k}" for k in teller_fields if k != "id")

        sql = f"""
            INSERT INTO transactions ({columns}) VALUES ({placeholders})
            ON CONFLICT(id) DO UPDATE SET {updates}
        """
        self._execute(sql, [data[k] for k in teller_fields])

    def update_transaction_category(self, transaction_id: str, category: str, confidence: float = None):
        """Set category and confidence for a transaction."""
        self._execute(
            "UPDATE transactions SET inferred_category = ?, confidence = ? WHERE id = ?",
            (category, confidence, transaction_id)
        )

    def clear_all_categories(self):
        """Clear all inferred_category and confidence values."""
        self._execute("UPDATE transactions SET inferred_category = NULL, confidence = NULL")

    def get_uncategorized_transactions(self):
        """Get transactions without a category, with account info."""
        return self._query("""
            SELECT t.id, t.description, t.amount, t.date, t.type, t.account_id,
                   a.name AS account_name, a.subtype AS account_subtype,
                   json_extract(t.details, '$.counterparty.name') AS counterparty,
                   a.last_four AS account_last_four
            FROM transactions t
            LEFT JOIN accounts a ON t.account_id = a.id
            WHERE t.inferred_category IS NULL
            ORDER BY t.date DESC
        """, as_row=True)

    def add_transaction(self, data: dict):
        """Insert a transaction directly (for testing)."""
        prepared = {}
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                prepared[key] = json.dumps(value)
            elif isinstance(value, date):
                prepared[key] = value.isoformat()
            else:
                prepared[key] = value
        columns = ", ".join(prepared.keys())
        placeholders = ", ".join(["?"] * len(prepared))
        self._execute(f"INSERT INTO transactions ({columns}) VALUES ({placeholders})", list(prepared.values()))

    def get_transactions_for_export(self):
        """Get all transactions with account info for CSV export."""
        return self._query("""
            SELECT t.id, t.date, t.description, t.amount, t.inferred_category, t.confidence,
                   json_extract(t.details, '$.counterparty.name') as counterparty,
                   a.name as account_name, a.subtype as account_subtype, a.last_four as account_last_four
            FROM transactions t
            LEFT JOIN accounts a ON t.account_id = a.id
            ORDER BY t.date DESC
        """)

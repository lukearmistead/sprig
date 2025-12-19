"""Database operations for Sprig."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sprig.logger import get_logger
from sprig.models import TellerAccount, TellerTransaction

logger = get_logger("sprig.database")


class Database:
    """SQLite connection and schema management."""

    ACCOUNTS_SCHEMA = """
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
    """

    TRANSACTIONS_SCHEMA = """
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
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._initialize()

    def _initialize(self):
        """Create database file and tables if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.execute(self.ACCOUNTS_SCHEMA)
            conn.execute(self.TRANSACTIONS_SCHEMA)
            conn.commit()

    @contextmanager
    def connect(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()


def _serialize_value(value: Any) -> Any:
    """Convert Python objects to SQLite-compatible values."""
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    if isinstance(value, date):
        return value.isoformat()
    return value


def _serialize_dict(data: Dict) -> Dict:
    """Serialize all values in a dictionary for SQL insertion."""
    return {k: _serialize_value(v) for k, v in data.items()}


class Accounts:
    """Account table operations."""

    def __init__(self, db: Database):
        self.db = db

    def save(self, account: TellerAccount) -> bool:
        """Save account to database (insert or replace)."""
        try:
            data = _serialize_dict(account.model_dump())
            columns = list(data.keys())
            placeholders = ["?" for _ in columns]
            values = list(data.values())

            sql = f"INSERT OR REPLACE INTO accounts ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
            with self.db.connect() as conn:
                conn.execute(sql, values)
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error saving account {account.id}: {e}")
            return False


class Transactions:
    """Transaction table operations."""

    def __init__(self, db: Database):
        self.db = db

    def sync(self, transaction: TellerTransaction) -> bool:
        """Sync transaction: update existing (preserving categories) or insert new."""
        try:
            data = _serialize_dict(transaction.model_dump())
            txn_id = data["id"]

            with self.db.connect() as conn:
                exists = conn.execute(
                    "SELECT 1 FROM transactions WHERE id = ?", (txn_id,)
                ).fetchone()

                if exists:
                    # Update existing, preserve categories
                    pairs = [f"{k} = ?" for k in data if k != "id"]
                    values = [v for k, v in data.items() if k != "id"] + [txn_id]
                    conn.execute(
                        f"UPDATE transactions SET {', '.join(pairs)} WHERE id = ?",
                        values,
                    )
                else:
                    # Insert new
                    columns = list(data.keys())
                    placeholders = ["?" for _ in columns]
                    conn.execute(
                        f"INSERT INTO transactions ({', '.join(columns)}) VALUES ({', '.join(placeholders)})",
                        list(data.values()),
                    )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error syncing transaction {transaction.id}: {e}")
            return False

    def add(self, data: Dict) -> bool:
        """Add a transaction directly (for testing/manual insertion)."""
        try:
            data = _serialize_dict(data)
            columns = list(data.keys())
            placeholders = ["?" for _ in columns]
            with self.db.connect() as conn:
                conn.execute(
                    f"INSERT INTO transactions ({', '.join(columns)}) VALUES ({', '.join(placeholders)})",
                    list(data.values()),
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding transaction: {e}")
            return False

    def update_category(
        self, transaction_id: str, category: str, confidence: Optional[float] = None
    ) -> bool:
        """Update category and confidence for a transaction."""
        try:
            with self.db.connect() as conn:
                conn.execute(
                    "UPDATE transactions SET inferred_category = ?, confidence = ? WHERE id = ?",
                    (category, confidence, transaction_id),
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating category for {transaction_id}: {e}")
            return False

    def clear_all_categories(self) -> int:
        """Clear all inferred_category and confidence values. Returns rows affected."""
        with self.db.connect() as conn:
            cursor = conn.execute(
                "UPDATE transactions SET inferred_category = NULL, confidence = NULL"
            )
            rows = cursor.rowcount
            conn.commit()
        return rows

    def get_uncategorized(self) -> List[Tuple]:
        """Get transactions without an inferred category, joined with account info."""
        with self.db.connect() as conn:
            cursor = conn.execute("""
                SELECT t.id, t.description, t.amount, t.date, t.type,
                       t.account_id, a.name, a.subtype,
                       json_extract(t.details, '$.counterparty.name') as counterparty,
                       a.last_four
                FROM transactions t
                LEFT JOIN accounts a ON t.account_id = a.id
                WHERE t.inferred_category IS NULL
                ORDER BY t.date DESC
            """)
            return cursor.fetchall()

    def get_for_export(self) -> List[Tuple]:
        """Get all transactions for export with account details."""
        with self.db.connect() as conn:
            cursor = conn.execute("""
                SELECT t.id, t.date, t.description, t.amount, t.inferred_category,
                       t.confidence,
                       json_extract(t.details, '$.counterparty.name') as counterparty,
                       a.name as account_name,
                       a.subtype as account_subtype,
                       a.last_four as account_last_four
                FROM transactions t
                LEFT JOIN accounts a ON t.account_id = a.id
                ORDER BY t.date DESC
            """)
            return cursor.fetchall()


# Backwards-compatible alias
class SprigDatabase:
    """Backwards-compatible wrapper for the refactored database layer."""

    def __init__(self, db_path: Path):
        self._db = Database(db_path)
        self._accounts = Accounts(self._db)
        self._transactions = Transactions(self._db)

    @property
    def connection(self):
        """Return a connection for direct SQL access (used in tests)."""
        return sqlite3.connect(self._db.db_path)

    def insert_record(self, table_name: str, data: Dict) -> bool:
        """Insert data into specified table."""
        try:
            data = _serialize_dict(data)
            columns = list(data.keys())
            placeholders = ["?" for _ in columns]
            values = list(data.values())
            sql = f"INSERT OR REPLACE INTO {table_name} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
            with self._db.connect() as conn:
                conn.execute(sql, values)
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error inserting into {table_name}: {e}")
            return False

    def sync_transaction(self, transaction) -> bool:
        if hasattr(transaction, "model_dump"):
            return self._transactions.sync(transaction)
        # Handle dict input
        return self._transactions.sync(TellerTransaction(**transaction))

    def add_transaction(self, transaction_data: Dict) -> bool:
        return self._transactions.add(transaction_data)

    def update_transaction_category(
        self, transaction_id: str, category: str, confidence: float = None
    ) -> bool:
        return self._transactions.update_category(transaction_id, category, confidence)

    def clear_all_categories(self) -> int:
        return self._transactions.clear_all_categories()

    def get_uncategorized_transactions(self) -> List[Tuple]:
        return self._transactions.get_uncategorized()

    def get_transactions_for_export(self) -> List[Tuple]:
        return self._transactions.get_for_export()

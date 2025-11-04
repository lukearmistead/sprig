"""Database operations for Sprig."""

import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import Dict


class SprigDatabase:
    """SQLite database for storing Teller data."""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._initialize_database()
    
    def _initialize_database(self):
        """Create database file and tables if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            # Create accounts table
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
            
            # Create transactions table
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
                    llm_category TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
    
    def insert_record(self, table_name: str, data: Dict) -> bool:
        """Insert data into specified table."""
        try:
            # Prepare data for SQL insertion
            insert_data = {}
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    insert_data[key] = json.dumps(value)
                elif isinstance(value, date):
                    insert_data[key] = value.isoformat()
                else:
                    insert_data[key] = value
            
            # Build and execute INSERT statement
            with sqlite3.connect(self.db_path) as conn:
                columns = list(insert_data.keys())
                placeholders = ["?" for _ in columns]
                values = list(insert_data.values())
                
                sql = f"INSERT OR REPLACE INTO {table_name} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
                conn.execute(sql, values)
                conn.commit()
                return True
                
        except Exception as e:
            print(f"Error inserting into {table_name}: {e}")
            return False
    
    def get_uncategorized_transactions(self):
        """Get transactions that don't have an LLM category assigned."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT id, description, amount, date, type 
                FROM transactions 
                WHERE llm_category IS NULL
                ORDER BY date DESC
            """)
            return cursor.fetchall()
    
    def update_transaction_category(self, transaction_id: str, category: str) -> bool:
        """Update the LLM category for a specific transaction."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "UPDATE transactions SET llm_category = ? WHERE id = ?",
                    (category, transaction_id)
                )
                conn.commit()
                return True
        except Exception as e:
            print(f"Error updating category for transaction {transaction_id}: {e}")
            return False
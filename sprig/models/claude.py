"""Pydantic models for Claude API data validation."""

from typing import List, Optional

from pydantic import BaseModel, Field


class TransactionCategory(BaseModel):
    """Single transaction categorization item."""
    transaction_id: str
    category: str
    confidence: float = Field(..., ge=0, le=1, description="Confidence score from 0 to 1")


class TransactionView(BaseModel):
    """Essential transaction data for categorization and CSV export.

    This model contains the 10 fields exported to CSV and sent to Claude for categorization.
    Fields are ordered to match the desired CSV column order.
    """
    id: str
    date: str  # Keep as string for simpler JSON
    description: str
    amount: float
    inferred_category: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0, le=1, description="Confidence score from 0 to 1")
    counterparty: Optional[str] = None
    account_name: Optional[str] = None
    account_subtype: Optional[str] = None
    account_last_four: Optional[str] = None

    @classmethod
    def from_db_row(cls, row):
        """Create TransactionView from sqlite3.Row object.

        Args:
            row: sqlite3.Row from get_uncategorized_transactions()

        Returns:
            TransactionView instance
        """
        return cls(
            id=row["id"],
            date=row["date"],
            description=row["description"],
            amount=row["amount"],
            inferred_category=None,
            confidence=None,
            counterparty=row["counterparty"],
            account_name=row["account_name"],
            account_subtype=row["account_subtype"],
            account_last_four=row["account_last_four"],
        )


class TransactionBatch(BaseModel):
    """Batch of transactions for AI categorization."""
    transactions: List[TransactionView]


class ClaudeAPIKey(BaseModel):
    """Validated Claude API key."""
    key: str = Field(..., pattern=r'^sk-ant-api03-[A-Za-z0-9\-]{95}$', description="Claude API keys start with 'sk-ant-api03-' followed by exactly 95 alphanumeric characters and dashes")


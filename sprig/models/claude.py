"""Pydantic models for Claude API data validation."""

from typing import List, Optional, Dict, Any

from pydantic import BaseModel


class TransactionCategory(BaseModel):
    """Single transaction categorization item."""
    transaction_id: str
    category: str


class TransactionView(BaseModel):
    """Essential transaction data for categorization and CSV export.

    This model contains the 9 fields exported to CSV and sent to Claude for categorization.
    Fields are ordered to match the desired CSV column order.
    """
    id: str
    date: str  # Keep as string for simpler JSON
    description: str
    amount: float
    inferred_category: Optional[str] = None
    counterparty: Optional[str] = None
    account_name: Optional[str] = None
    account_subtype: Optional[str] = None
    account_last_four: Optional[str] = None


class ClaudeContentBlock(BaseModel):
    """Claude API content block."""
    type: str
    text: str


class ClaudeResponse(BaseModel):
    """Claude API response."""
    id: str
    type: str
    role: str
    content: List[ClaudeContentBlock]
    model: str
    stop_reason: Optional[str] = None
    stop_sequence: Optional[str] = None
    usage: Dict[str, Any]

    @property
    def text(self) -> str:
        """Direct access to the first content block's text."""
        return self.content[0].text if self.content else ""


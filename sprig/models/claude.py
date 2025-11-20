"""Pydantic models for Claude API data validation."""

from typing import List, Optional, Dict, Any

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


class ClaudeContentBlock(BaseModel):
    """Claude API content block."""
    type: str
    text: str


class ClaudeAPIKey(BaseModel):
    """Validated Claude API key."""
    key: str = Field(..., pattern=r'^sk-ant-api03-[A-Za-z0-9\-]{95}$', description="Claude API keys start with 'sk-ant-api03-' followed by exactly 95 alphanumeric characters and dashes")


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


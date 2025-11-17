"""Pydantic models for Claude API data validation."""

from typing import List, Optional, Dict, Any

from pydantic import BaseModel


class TransactionCategory(BaseModel):
    """Single transaction categorization item."""
    transaction_id: str
    category: str


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


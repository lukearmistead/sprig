"""Pydantic models for Teller API data validation."""

from datetime import date
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class TellerAccount(BaseModel):
    """Teller API account response."""
    
    id: str
    name: str
    type: str
    subtype: Optional[str] = None
    institution: Optional[Dict[str, Any]] = None
    enrollment_id: Optional[str] = None
    currency: str = Field(..., pattern=r'^[A-Z]{3}$')
    status: str
    last_four: Optional[str] = Field(None, pattern=r'^\d{4}$')
    links: Optional[Dict[str, Any]] = None


class TellerTransaction(BaseModel):
    """Teller API transaction response."""

    id: str
    account_id: str
    amount: float
    description: str
    date: date
    type: str
    status: str
    details: Optional[Dict[str, Any]] = None
    running_balance: Optional[float] = None
    links: Optional[Dict[str, Any]] = None


class TellerAccessToken(BaseModel):
    """Validated Teller access token."""
    token: str = Field(..., pattern=r'^token_[a-z0-9]{26}$', description="Teller access tokens start with 'token_' followed by exactly 26 lowercase alphanumeric characters")
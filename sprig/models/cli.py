"""CLI parameter models with Pydantic validation."""

from typing import Optional

from pydantic import BaseModel, Field, PastDate


class SyncParams(BaseModel):
    """Parameters for the sync command with validation."""

    recategorize: bool = Field(default=False)
    from_date: Optional[PastDate] = Field(default=None)

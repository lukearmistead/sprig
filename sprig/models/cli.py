"""CLI parameter models with Pydantic validation."""

from typing import Optional

from pydantic import BaseModel, Field, PastDate


class SyncParams(BaseModel):
    """Parameters for the sync command with validation.

    Pydantic automatically handles:
    - Parsing YYYY-MM-DD strings to date objects
    - Rejecting invalid date formats
    - Validating leap years and date boundaries
    - Ensuring from_date is in the past (using PastDate type)

    Attributes:
        recategorize: Clear all existing categories before syncing
        from_date: Only sync transactions from this past date onwards
    """

    recategorize: bool = Field(default=False)
    from_date: Optional[PastDate] = Field(
        default=None,
        description="Only sync transactions from this past date onwards"
    )

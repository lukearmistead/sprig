"""CLI parameter models with Pydantic validation."""

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class SyncParams(BaseModel):
    """Parameters for the sync command with validation.

    Pydantic automatically handles:
    - Parsing YYYY-MM-DD strings to date objects
    - Rejecting invalid date formats
    - Validating leap years and date boundaries

    Attributes:
        recategorize: Clear all existing categories before syncing
        from_date: Only sync transactions from this date onwards (today or earlier)
    """

    recategorize: bool = Field(default=False)
    from_date: Optional[date] = Field(
        default=None,
        description="Only sync transactions from this date onwards"
    )

    @field_validator('from_date')
    @classmethod
    def validate_date_not_future(cls, v: Optional[date]) -> Optional[date]:
        """Ensure from_date is not in the future (allows today).

        Note: We allow today's date since users may want to sync "from today onwards".
        If you need strictly past dates, use Pydantic's built-in PastDate type instead.

        Args:
            v: Date to validate

        Returns:
            The validated date

        Raises:
            ValueError: If date is in the future
        """
        if v is not None and v > date.today():
            raise ValueError(
                f"from_date cannot be in the future. Got {v}, today is {date.today()}"
            )
        return v

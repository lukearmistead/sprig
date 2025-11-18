"""CLI parameter models with Pydantic validation."""

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class SyncParams(BaseModel):
    """Parameters for the sync command with validation.

    Attributes:
        recategorize: Clear all existing categories before syncing
        from_date: Only sync transactions from this date onwards
    """

    recategorize: bool = Field(default=False)
    from_date: Optional[date] = Field(default=None)

    @field_validator('from_date', mode='before')
    @classmethod
    def parse_date_string(cls, v):
        """Parse date string in YYYY-MM-DD format.

        Args:
            v: Date string or date object

        Returns:
            date object

        Raises:
            ValueError: If date string is invalid
        """
        if v is None:
            return None

        if isinstance(v, date):
            return v

        if isinstance(v, str):
            try:
                # Pydantic will handle the actual parsing
                return v
            except Exception as e:
                raise ValueError(
                    f"Invalid date format: {v}. Please use YYYY-MM-DD format (e.g., 2024-01-15)"
                ) from e

        raise ValueError(f"Expected date string or date object, got {type(v)}")

    @field_validator('from_date')
    @classmethod
    def validate_date_not_future(cls, v):
        """Ensure from_date is not in the future.

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

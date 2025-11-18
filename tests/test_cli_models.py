"""Tests for CLI parameter models."""

import pytest
from datetime import date, timedelta
from pydantic import ValidationError

from sprig.models.cli import SyncParams


class TestSyncParams:
    """Test suite for SyncParams validation."""

    def test_valid_params_with_date_string(self):
        """Test valid parameters with date as string."""
        params = SyncParams(
            recategorize=True,
            from_date="2024-01-15"
        )
        assert params.recategorize is True
        assert params.from_date == date(2024, 1, 15)

    def test_valid_params_with_date_object(self):
        """Test valid parameters with date object."""
        test_date = date(2024, 1, 15)
        params = SyncParams(
            recategorize=False,
            from_date=test_date
        )
        assert params.recategorize is False
        assert params.from_date == test_date

    def test_valid_params_with_none_date(self):
        """Test valid parameters with None date."""
        params = SyncParams(
            recategorize=False,
            from_date=None
        )
        assert params.recategorize is False
        assert params.from_date is None

    def test_default_values(self):
        """Test default parameter values."""
        params = SyncParams()
        assert params.recategorize is False
        assert params.from_date is None

    def test_invalid_date_format(self):
        """Test that invalid date format raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SyncParams(from_date="2024/01/15")

        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert 'from_date' in str(errors[0]['loc'])

    def test_invalid_date_format_wrong_order(self):
        """Test that date in wrong order raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SyncParams(from_date="15-01-2024")

        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert 'from_date' in str(errors[0]['loc'])

    def test_invalid_date_format_with_text(self):
        """Test that text date raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SyncParams(from_date="January 15, 2024")

        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert 'from_date' in str(errors[0]['loc'])

    def test_future_date_raises_error(self):
        """Test that future date raises ValidationError."""
        future_date = date.today() + timedelta(days=30)
        with pytest.raises(ValidationError) as exc_info:
            SyncParams(from_date=future_date)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert 'from_date' in str(errors[0]['loc'])
        assert 'future' in errors[0]['msg'].lower()

    def test_future_date_string_raises_error(self):
        """Test that future date string raises ValidationError."""
        future_date = date.today() + timedelta(days=30)
        with pytest.raises(ValidationError) as exc_info:
            SyncParams(from_date=future_date.isoformat())

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert 'from_date' in str(errors[0]['loc'])
        assert 'future' in errors[0]['msg'].lower()

    def test_today_is_valid(self):
        """Test that today's date is valid."""
        params = SyncParams(from_date=date.today())
        assert params.from_date == date.today()

    def test_past_date_is_valid(self):
        """Test that past dates are valid."""
        past_date = date.today() - timedelta(days=30)
        params = SyncParams(from_date=past_date)
        assert params.from_date == past_date

    def test_recategorize_flag(self):
        """Test recategorize flag validation."""
        params1 = SyncParams(recategorize=True)
        assert params1.recategorize is True

        params2 = SyncParams(recategorize=False)
        assert params2.recategorize is False

    def test_combined_valid_params(self):
        """Test valid parameters combined."""
        params = SyncParams(
            recategorize=True,
            from_date="2024-01-01"
        )
        assert params.recategorize is True
        assert params.from_date == date(2024, 1, 1)

    def test_year_boundary_dates(self):
        """Test dates at year boundaries."""
        params1 = SyncParams(from_date="2024-01-01")
        assert params1.from_date == date(2024, 1, 1)

        params2 = SyncParams(from_date="2023-12-31")
        assert params2.from_date == date(2023, 12, 31)

    def test_leap_year_date(self):
        """Test leap year date validation."""
        params = SyncParams(from_date="2024-02-29")
        assert params.from_date == date(2024, 2, 29)

    def test_invalid_leap_year_date(self):
        """Test invalid leap year date raises error."""
        with pytest.raises(ValidationError):
            SyncParams(from_date="2023-02-29")

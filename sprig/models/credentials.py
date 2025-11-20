"""Individual credential models for validation."""

from pathlib import Path
from pydantic import BaseModel, Field


class TellerAppId(BaseModel):
    """Teller application ID."""
    value: str = Field(pattern=r"^app_[a-z0-9]{32}$")


class ClaudeAPIKey(BaseModel):
    """Claude API key."""
    value: str = Field(pattern=r"^sk-ant-api03-[A-Za-z0-9_-]{95}$")


class CertPath(BaseModel):
    """Certificate file path."""
    value: Path


class KeyPath(BaseModel):
    """Private key file path."""
    value: Path


class DatabasePath(BaseModel):
    """Database file path."""
    value: Path


class Environment(BaseModel):
    """Environment setting."""
    value: str = Field(pattern=r"^(development|sandbox|production)$")

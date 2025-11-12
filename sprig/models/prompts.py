"""Pydantic models for prompt configuration."""

from typing import Dict, List
from pydantic import BaseModel, Field, field_validator


class PromptConfig(BaseModel):
    """Configuration for a single prompt template."""
    
    template: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    max_tokens: int = Field(..., gt=0)
    guidelines: List[str] = Field(default_factory=list)
    
    @field_validator('max_tokens')
    @classmethod
    def validate_max_tokens(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("max_tokens must be positive")
        return v


class PromptsCatalogConfig(BaseModel):
    """Container for all prompt configurations."""
    
    prompts: Dict[str, PromptConfig]
    
    @field_validator('prompts')
    @classmethod
    def validate_prompts_not_empty(cls, v: Dict[str, PromptConfig]) -> Dict[str, PromptConfig]:
        if not v:
            raise ValueError("prompts dictionary cannot be empty")
        return v
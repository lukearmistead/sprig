"""Tests for prompt catalog and Pydantic models."""

import pytest
from pathlib import Path
import tempfile
import yaml

from sprig.models.prompts import PromptConfig, PromptsCatalogConfig
from sprig.prompt_catalog import PromptCatalog


class TestPromptConfig:
    """Test Pydantic models for prompt configuration."""
    
    def test_prompt_config_validates_required_fields(self):
        """Should validate required fields for a prompt configuration."""
        config = PromptConfig(
            template="Test prompt {variable}",
            model="claude-3-haiku-20240307",
            max_tokens=1000,
            guidelines=["Guideline 1", "Guideline 2"]
        )
        
        assert config.template == "Test prompt {variable}"
        assert config.model == "claude-3-haiku-20240307"
        assert config.max_tokens == 1000
        assert len(config.guidelines) == 2
    
    def test_prompt_config_rejects_invalid_max_tokens(self):
        """Should reject negative or zero max_tokens."""
        with pytest.raises(ValueError):
            PromptConfig(
                template="Test",
                model="claude-3-haiku",
                max_tokens=-1,
                guidelines=[]
            )
    
    def test_prompts_catalog_config_loads_multiple_prompts(self):
        """Should load multiple prompts from configuration."""
        config_data = {
            "categorization": {
                "template": "Categorize: {transactions}",
                "model": "claude-3-haiku-20240307",
                "max_tokens": 1000,
                "guidelines": ["Use categories"]
            },
            "summary": {
                "template": "Summarize: {text}",
                "model": "claude-3-opus-20240307",
                "max_tokens": 500,
                "guidelines": []
            }
        }
        
        catalog = PromptsCatalogConfig(prompts=config_data)
        assert "categorization" in catalog.prompts
        assert "summary" in catalog.prompts
        assert catalog.prompts["categorization"].model == "claude-3-haiku-20240307"


class TestPromptCatalog:
    """Test PromptCatalog functionality."""
    
    def test_loads_prompts_from_yaml_config(self, tmp_path):
        """Should load prompts from YAML configuration file."""
        config_content = """
categories:
  dining: "Restaurants and food"
  groceries: "Supermarkets"

prompts:
  categorization:
    template: |
      Categorize these transactions: {transactions}
      Available categories: {categories}
    model: claude-3-haiku-20240307
    max_tokens: 1000
    guidelines:
      - Use dining for restaurants
      - Use groceries for supermarkets
"""
        config_file = tmp_path / "config.yml"
        config_file.write_text(config_content)
        
        catalog = PromptCatalog(config_path=config_file)
        prompt = catalog.get_prompt("categorization")
        
        assert prompt.model == "claude-3-haiku-20240307"
        assert prompt.max_tokens == 1000
        assert "Categorize these transactions" in prompt.template
        assert len(prompt.guidelines) == 2
    
    def test_get_prompt_raises_for_missing_prompt(self, tmp_path):
        """Should raise KeyError for non-existent prompt."""
        config_content = """
prompts:
  categorization:
    template: "Test"
    model: "claude-3-haiku"
    max_tokens: 100
    guidelines: []
"""
        config_file = tmp_path / "config.yml"
        config_file.write_text(config_content)
        
        catalog = PromptCatalog(config_path=config_file)
        
        with pytest.raises(KeyError) as exc_info:
            catalog.get_prompt("nonexistent")
        assert "nonexistent" in str(exc_info.value)
    
    def test_render_template_substitutes_variables(self, tmp_path):
        """Should render template with provided variables."""
        config_content = """
prompts:
  test:
    template: "Hello {name}, you have {count} items"
    model: "test-model"
    max_tokens: 100
    guidelines: []
"""
        config_file = tmp_path / "config.yml"
        config_file.write_text(config_content)
        
        catalog = PromptCatalog(config_path=config_file)
        rendered = catalog.render_template("test", name="Alice", count=5)
        
        assert rendered == "Hello Alice, you have 5 items"
    
    def test_render_template_with_missing_variables_raises(self, tmp_path):
        """Should raise KeyError when template variables are missing."""
        config_content = """
prompts:
  test:
    template: "Hello {name}"
    model: "test-model"
    max_tokens: 100
    guidelines: []
"""
        config_file = tmp_path / "config.yml"
        config_file.write_text(config_content)
        
        catalog = PromptCatalog(config_path=config_file)
        
        with pytest.raises(KeyError):
            catalog.render_template("test")  # Missing 'name' variable
    
    def test_format_categories_returns_formatted_string(self, tmp_path):
        """Should format categories with descriptions."""
        config_content = """
categories:
  dining: "Restaurants and food delivery"
  groceries: "Supermarkets and food stores"
  fuel: "Gas stations"

prompts:
  test:
    template: "Test"
    model: "test-model"
    max_tokens: 100
    guidelines: []
"""
        config_file = tmp_path / "config.yml"
        config_file.write_text(config_content)
        
        catalog = PromptCatalog(config_path=config_file)
        formatted = catalog.format_categories()
        
        assert "dining: Restaurants and food delivery" in formatted
        assert "groceries: Supermarkets and food stores" in formatted
        assert "fuel: Gas stations" in formatted
    
    def test_format_transactions_returns_json(self, tmp_path):
        """Should format transactions as JSON string."""
        from sprig.models.teller import TellerTransaction
        from datetime import datetime
        
        config_content = """
prompts:
  test:
    template: "Test"
    model: "test-model"
    max_tokens: 100
    guidelines: []
"""
        config_file = tmp_path / "config.yml"
        config_file.write_text(config_content)
        
        catalog = PromptCatalog(config_path=config_file)
        
        transactions = [
            TellerTransaction(
                account_id="acc_123",
                amount=50.00,
                date="2024-01-01",
                description="Test transaction",
                id="txn_123",
                status="posted",
                type="debit"
            )
        ]
        
        formatted = catalog.format_transactions(transactions)
        
        assert "txn_123" in formatted
        assert "Test transaction" in formatted
        assert "50.0" in formatted
    
    def test_catalog_handles_missing_prompts_section(self, tmp_path):
        """Should raise ValueError if config lacks prompts section."""
        config_content = """
categories:
  dining: "Restaurants"
"""
        config_file = tmp_path / "config.yml"
        config_file.write_text(config_content)
        
        with pytest.raises(ValueError) as exc_info:
            PromptCatalog(config_path=config_file)
        assert "prompts" in str(exc_info.value).lower()
    
    def test_catalog_uses_default_path_when_not_specified(self, monkeypatch):
        """Should use default config.yml path when not specified."""
        # Create a mock config in the expected default location
        mock_config = """
prompts:
  test:
    template: "Default template"
    model: "test-model"
    max_tokens: 100
    guidelines: []
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(mock_config)
            temp_path = Path(f.name)
        
        # Monkeypatch the default path calculation
        def mock_default_path(self):
            return temp_path
        
        monkeypatch.setattr("sprig.prompt_catalog.PromptCatalog._default_config_path", mock_default_path)
        
        try:
            catalog = PromptCatalog()
            prompt = catalog.get_prompt("test")
            assert prompt.template == "Default template"
        finally:
            temp_path.unlink()
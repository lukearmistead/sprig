"""Prompt catalog for managing and rendering prompt templates."""

import json
from pathlib import Path
from typing import Dict, List

import yaml

from sprig.models.prompts import PromptConfig, PromptsCatalogConfig
from sprig.models.teller import TellerTransaction


class PromptCatalog:
    """Catalog for loading and rendering prompt templates."""
    
    def __init__(self, config_path: Path = None):
        """Initialize the prompt catalog.
        
        Args:
            config_path: Path to config.yml file. Uses default if not specified.
        """
        self.config_path = config_path or self._default_config_path()
        self._config_data = self._load_config()
        self._prompts_config = self._load_prompts()
        self._categories = self._load_categories()
    
    def _default_config_path(self) -> Path:
        """Get the default config.yml path."""
        return Path(__file__).parent.parent / "config.yml"
    
    def _load_config(self) -> Dict:
        """Load the full configuration from YAML file."""
        with open(self.config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        if not isinstance(config_data, dict):
            raise ValueError("Configuration file must contain a YAML dictionary")
            
        return config_data
    
    def _load_prompts(self) -> PromptsCatalogConfig:
        """Load and validate prompts configuration."""
        if 'prompts' not in self._config_data:
            raise ValueError("Configuration must contain a 'prompts' section")
        
        prompts_data = self._config_data['prompts']
        
        # Convert dict to PromptConfig objects
        prompts_dict = {}
        for name, config in prompts_data.items():
            prompts_dict[name] = PromptConfig(**config)
        
        return PromptsCatalogConfig(prompts=prompts_dict)
    
    def _load_categories(self) -> Dict[str, str]:
        """Load categories from config for formatting."""
        return self._config_data.get('categories', {})
    
    def get_prompt(self, prompt_name: str) -> PromptConfig:
        """Get a prompt configuration by name.
        
        Args:
            prompt_name: Name of the prompt to retrieve
            
        Returns:
            PromptConfig for the specified prompt
            
        Raises:
            KeyError: If prompt_name doesn't exist
        """
        if prompt_name not in self._prompts_config.prompts:
            raise KeyError(f"Prompt '{prompt_name}' not found in catalog")
        
        return self._prompts_config.prompts[prompt_name]
    
    def render_template(self, prompt_name: str, **kwargs) -> str:
        """Render a prompt template with provided variables.
        
        Args:
            prompt_name: Name of the prompt to render
            **kwargs: Template variables to substitute
            
        Returns:
            Rendered prompt string
            
        Raises:
            KeyError: If prompt_name doesn't exist or required variables are missing
        """
        prompt_config = self.get_prompt(prompt_name)
        
        try:
            return prompt_config.template.format(**kwargs)
        except KeyError as e:
            raise KeyError(f"Missing template variable: {e}")
    
    def format_categories(self) -> str:
        """Format categories with descriptions for prompts.
        
        Returns:
            Formatted string with category: description pairs
        """
        formatted_categories = []
        for name, description in self._categories.items():
            formatted_categories.append(f"{name}: {description}")
        
        return ", ".join(formatted_categories)
    
    def format_transactions(self, transactions: List[TellerTransaction]) -> str:
        """Format transactions as JSON string for prompts.
        
        Args:
            transactions: List of transactions to format
            
        Returns:
            JSON string representation of transactions
        """
        transaction_data = [txn.model_dump() for txn in transactions]
        return json.dumps(transaction_data, indent=2, default=str)
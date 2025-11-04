"""Tests for sprig.config module."""

from sprig.models import RuntimeConfig


def test_config_load():
    """Test that Config.load() works correctly."""
    config = RuntimeConfig.load()
    
    assert config.app_id
    assert len(config.access_tokens) > 0
    assert config.environment in ["sandbox", "development", "production"]
    assert config.cert_path.exists()
    assert config.key_path.exists()
    assert config.database_path.name == "sprig.db"
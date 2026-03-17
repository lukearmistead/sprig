"""Test configuration — use repo root config-template.yml for all tests."""

from pathlib import Path
from unittest.mock import patch

import pytest

REPO_CONFIG = Path(__file__).parent.parent / "config-template.yml"

TEST_OVERRIDES = {"teller_app_id": "app_test", "claude_key": "sk-test"}


@pytest.fixture(autouse=True)
def use_repo_config():
    from sprig.models.config import Config

    original_init = Config.__init__

    def _patched_init(self, **kwargs):
        for k, v in TEST_OVERRIDES.items():
            if not kwargs.get(k):
                kwargs[k] = v
        original_init(self, **kwargs)

    with patch("sprig.paths.get_sprig_home", return_value=REPO_CONFIG.parent), \
         patch.object(Config, "__init__", _patched_init):
        yield

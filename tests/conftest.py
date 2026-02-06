"""Test configuration — use repo root config-template.yml for all tests."""

from pathlib import Path
from unittest.mock import patch

import pytest

REPO_CONFIG = Path(__file__).parent.parent / "config-template.yml"


@pytest.fixture(autouse=True)
def use_repo_config():
    with patch("sprig.paths.get_sprig_home", return_value=REPO_CONFIG.parent):
        yield

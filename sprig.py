#!/usr/bin/env python3
"""Sprig CLI entry point for development."""

import sys
from pathlib import Path

# Add the sprig package to the path for development
sys.path.insert(0, str(Path(__file__).parent))

from sprig.cli import main

if __name__ == "__main__":
    main()

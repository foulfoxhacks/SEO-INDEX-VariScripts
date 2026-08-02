#!/usr/bin/env python3
"""Backward-compatible launcher for the canonical IndexNow runner in Scripts/."""
from __future__ import annotations

import runpy
import sys
from pathlib import Path


SCRIPTS = Path(__file__).resolve().with_name("Scripts")
RUNNER = SCRIPTS / "indexnow_runner.py"

if __name__ == "__main__":
    sys.path.insert(0, str(SCRIPTS))
    runpy.run_path(str(RUNNER), run_name="__main__")

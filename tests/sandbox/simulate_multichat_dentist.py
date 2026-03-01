#!/usr/bin/env python3
"""
Compatibility wrapper.
Use the new path: tests/sandbox/dentist/simulate_multichat_dentist.py
"""

from pathlib import Path
import runpy
import sys


TARGET_DIR = Path(__file__).parent / "dentist"
sys.path.insert(0, str(TARGET_DIR))
TARGET = TARGET_DIR / "simulate_multichat_dentist.py"
runpy.run_path(str(TARGET), run_name="__main__")

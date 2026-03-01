#!/usr/bin/env python3
"""
Compatibility wrapper.
Use the new path: tests/sandbox/dentist/simulate_chat_dentist.py
"""

from pathlib import Path
import runpy


TARGET = Path(__file__).parent / "dentist" / "simulate_chat_dentist.py"
runpy.run_path(str(TARGET), run_name="__main__")

#!/usr/bin/env python3
"""
Compatibility wrapper.
Use the new path: tests/sandbox/realtor/simulate_chat_realtor.py
"""

from pathlib import Path
import runpy


TARGET = Path(__file__).parent / "realtor" / "simulate_chat_realtor.py"
runpy.run_path(str(TARGET), run_name="__main__")

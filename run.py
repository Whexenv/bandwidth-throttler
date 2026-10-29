#!/usr/bin/env python3
"""
Bandwidth Throttler - Python Desktop Application
Main Entry Point
"""

import sys
import os

# Ensure the root project directory is in the module search path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ui.app import launch

if __name__ == "__main__":
    launch()


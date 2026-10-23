"""Pytest configuration and shared fixtures (populated in Phase 1)."""
import sys
import os

# Make sure the backend/app package is importable from tests/
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

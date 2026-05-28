# conftest.py — root-level pytest configuration
# Ensures the backend/ directory is always on sys.path for test discovery.
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

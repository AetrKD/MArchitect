"""Shared Java staging location without importing API/task modules."""
import os
from pathlib import Path

JAVA_INSTALL_DIR = Path(os.getenv("MARCHITECT_JAVA_INSTALL_DIR", "/java"))

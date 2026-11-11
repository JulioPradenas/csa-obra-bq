"""Deja importables los scripts del lab."""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "scripts"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

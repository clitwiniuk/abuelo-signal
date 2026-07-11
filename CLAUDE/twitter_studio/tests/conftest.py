"""Pytest bootstrap — point the app at a throwaway SQLite file before any
project module (which creates its SQLAlchemy engine at import time) is
imported. Never run tests against twitter_studio.db.
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

_TMP_DB = Path(tempfile.mkdtemp()) / "test_twitter_studio.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB}"

import pytest

from database.schema import init_db


@pytest.fixture(autouse=True, scope="session")
def _init_test_db():
    init_db()

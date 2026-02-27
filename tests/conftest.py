from __future__ import annotations

import os
from pathlib import Path


def pytest_configure() -> None:
    db_path = Path.cwd() / ".pytest-kidtube.db"
    os.environ.setdefault("KIDTUBE_DB_PATH", str(db_path))

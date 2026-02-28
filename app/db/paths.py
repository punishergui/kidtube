from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path


def resolve_db_path(environ: Mapping[str, str] | None = None) -> Path:
    env = os.environ if environ is None else environ
    configured = env.get("KIDTUBE_DB_PATH") or env.get("SQLITE_PATH")
    if configured:
        return Path(configured)
    return Path("./data/kidtube.db")


def ensure_db_parent_writable(db_path: Path) -> None:
    parent = db_path.parent
    if parent.exists():
        if not os.access(parent, os.W_OK):
            raise RuntimeError(
                f"Database directory '{parent}' is not writable. "
                "Fix volume ownership/permissions or set KIDTUBE_DB_PATH to a writable path."
            )
        return

    if parent == Path("/data") and not os.access(Path("/"), os.W_OK):
        raise RuntimeError(
            "Database directory '/data' is not writable and cannot be created by the current user. "
            "Fix volume ownership/permissions or set KIDTUBE_DB_PATH to a writable path."
        )

    try:
        parent.mkdir(parents=True, exist_ok=True)
    except (PermissionError, OSError) as exc:
        raise RuntimeError(
            f"Database directory '{parent}' is not writable. "
            "Fix volume ownership/permissions or set KIDTUBE_DB_PATH to a writable path."
        ) from exc

    if not os.access(parent, os.W_OK):
        raise RuntimeError(
            f"Database directory '{parent}' is not writable after creation. "
            "Fix volume ownership/permissions or set KIDTUBE_DB_PATH to a writable path."
        )

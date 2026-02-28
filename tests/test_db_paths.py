from __future__ import annotations

from pathlib import Path

import pytest

from app.db.paths import ensure_db_parent_writable, resolve_db_path


def test_resolve_db_path_precedence() -> None:
    assert resolve_db_path({"KIDTUBE_DB_PATH": "/data/a.db", "SQLITE_PATH": "/data/b.db"}) == Path(
        "/data/a.db"
    )
    assert resolve_db_path({"SQLITE_PATH": "/data/b.db"}) == Path("/data/b.db")
    assert resolve_db_path({}) == Path("./data/kidtube.db")


def test_ensure_db_parent_writable_creates_missing_directory(tmp_path: Path) -> None:
    db_path = tmp_path / "missing" / "kidtube.db"
    ensure_db_parent_writable(db_path)
    assert db_path.parent.exists()


def test_ensure_db_parent_writable_fails_when_not_writable(monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = Path("/nonwritable/kidtube.db")

    def fake_access(_path: Path, _mode: int) -> bool:
        return False

    monkeypatch.setattr("app.db.paths.os.access", fake_access)

    with pytest.raises(RuntimeError, match="not writable"):
        ensure_db_parent_writable(db_path)

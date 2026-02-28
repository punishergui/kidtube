from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app


def test_startup_creates_missing_db_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "newdata" / "kidtube.db"

    monkeypatch.setattr("app.main.settings.database_url", f"sqlite:///{db_path}")
    monkeypatch.setattr("app.main.settings.sync_enabled", False)
    monkeypatch.setattr("app.main.run_migrations", lambda *_args, **_kwargs: None)

    with TestClient(app):
        pass

    assert db_path.parent.exists()


def test_startup_fails_with_clear_error_on_non_writable_db_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "newdata" / "kidtube.db"

    monkeypatch.setattr("app.main.settings.database_url", f"sqlite:///{db_path}")
    monkeypatch.setattr("app.main.settings.sync_enabled", False)
    monkeypatch.setattr("app.main.run_migrations", lambda *_args, **_kwargs: None)

    def fail_writable(_path: Path) -> None:
        raise RuntimeError("Database directory '/tmp/nonwritable' is not writable.")

    monkeypatch.setattr("app.main.ensure_db_parent_writable", fail_writable)

    with pytest.raises(SystemExit, match="not writable"):
        with TestClient(app):
            pass

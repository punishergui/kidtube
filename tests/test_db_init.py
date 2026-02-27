from pathlib import Path

from sqlalchemy import text
from sqlmodel import Session, create_engine

from app.db.migrate import run_migrations


def test_migrations_create_phase_one_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")

    run_migrations(engine, Path("app/db/migrations"))

    expected_tables = {
        "kids",
        "channels",
        "videos",
        "watch_log",
        "requests",
        "schema_migrations",
    }

    with Session(engine) as session:
        rows = session.exec(text("SELECT name FROM sqlite_master WHERE type='table'")).all()
    found_tables = {row[0] for row in rows}
    assert expected_tables.issubset(found_tables)

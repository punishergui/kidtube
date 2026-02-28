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
        rows = session.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        found_tables = {row[0] for row in rows}
        channel_columns = {row[1] for row in session.execute(text("PRAGMA table_info(channels)"))}
        indexes = {row[1] for row in session.execute(text("PRAGMA index_list('videos')"))}

    assert expected_tables.issubset(found_tables)
    assert {
        "input",
        "resolved_at",
        "resolve_status",
        "resolve_error",
        "allowed",
        "blocked",
        "blocked_at",
        "blocked_reason",
    }.issubset(channel_columns)
    assert "idx_videos_channel_published_at" in indexes

    with Session(engine) as session:
        channel_indexes = {row[1] for row in session.execute(text("PRAGMA index_list('channels')"))}

    assert "idx_channels_allowed_blocked_enabled" in channel_indexes

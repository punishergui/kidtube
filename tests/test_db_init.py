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
        "categories",
        "kid_schedules",
        "kid_category_limits",
        "kid_bonus_time",
        "search_log",
        "requests",
        "schema_migrations",
    }

    with Session(engine) as session:
        rows = session.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        found_tables = {row[0] for row in rows}
        channel_columns = {row[1] for row in session.execute(text("PRAGMA table_info(channels)"))}
        watch_log_columns = {
            row[1] for row in session.execute(text("PRAGMA table_info(watch_log)"))
        }
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
        "category_id",
    }.issubset(channel_columns)
    assert "idx_videos_channel_published_at" in indexes
    assert {"seconds_watched", "created_at", "category_id"}.issubset(watch_log_columns)

    with Session(engine) as session:
        channel_indexes = {
            row[1] for row in session.execute(text("PRAGMA index_list('channels')"))
        }
        search_log_indexes = {
            row[1] for row in session.execute(text("PRAGMA index_list('search_log')"))
        }
        watch_log_indexes = {
            row[1] for row in session.execute(text("PRAGMA index_list('watch_log')"))
        }

    assert "idx_channels_allowed_blocked_enabled" in channel_indexes
    assert "idx_channels_category_id" in channel_indexes
    assert "idx_search_log_kid_created_at" in search_log_indexes
    assert "idx_watch_log_kid_created_at" in watch_log_indexes


    with Session(engine) as session:
        default_categories = {
            row[0] for row in session.execute(text("SELECT name FROM categories"))
        }

    assert {"education", "fun"}.issubset(default_categories)

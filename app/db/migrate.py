from __future__ import annotations

from pathlib import Path

from sqlalchemy import text
from sqlmodel import Session


def run_migrations(engine, migrations_dir: Path) -> None:  # type: ignore[no-untyped-def]
    migrations = sorted(migrations_dir.glob("*.sql"))
    if not migrations:
        return

    with Session(engine) as session:
        session.exec(
            text(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    filename TEXT PRIMARY KEY,
                    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        session.commit()

        applied = {
            row[0] for row in session.exec(text("SELECT filename FROM schema_migrations")).all()
        }

        for migration in migrations:
            if migration.name in applied:
                continue
            sql = migration.read_text(encoding="utf-8")
            statements = [stmt.strip() for stmt in sql.split(";") if stmt.strip()]
            for statement in statements:
                session.exec(text(statement))
            session.exec(
                text("INSERT INTO schema_migrations (filename) VALUES (:filename)"),
                {"filename": migration.name},
            )
            session.commit()

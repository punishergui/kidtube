ALTER TABLE videos ADD COLUMN duration_seconds INTEGER;
ALTER TABLE videos ADD COLUMN is_short INTEGER NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS parent_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    shorts_enabled INTEGER NOT NULL DEFAULT 1
);
INSERT OR IGNORE INTO parent_settings(id, shorts_enabled) VALUES (1, 1);

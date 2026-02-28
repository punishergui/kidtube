CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    enabled INTEGER NOT NULL DEFAULT 1,
    daily_limit_minutes INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS kid_schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kid_id INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL CHECK(day_of_week BETWEEN 0 AND 6),
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(kid_id) REFERENCES kids(id)
);

CREATE TABLE IF NOT EXISTS kid_category_limits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kid_id INTEGER NOT NULL,
    category_id INTEGER NOT NULL,
    daily_limit_minutes INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(kid_id) REFERENCES kids(id),
    FOREIGN KEY(category_id) REFERENCES categories(id),
    UNIQUE(kid_id, category_id)
);

CREATE TABLE IF NOT EXISTS kid_bonus_time (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kid_id INTEGER NOT NULL,
    minutes INTEGER NOT NULL,
    expires_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(kid_id) REFERENCES kids(id)
);

CREATE TABLE IF NOT EXISTS search_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kid_id INTEGER NOT NULL,
    query TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(kid_id) REFERENCES kids(id)
);

ALTER TABLE watch_log ADD COLUMN seconds_watched INTEGER;
UPDATE watch_log SET seconds_watched = watched_seconds WHERE seconds_watched IS NULL;
ALTER TABLE watch_log ADD COLUMN created_at TEXT;
UPDATE watch_log SET created_at = watched_at WHERE created_at IS NULL;
ALTER TABLE watch_log ADD COLUMN category_id INTEGER REFERENCES categories(id);

CREATE INDEX IF NOT EXISTS idx_categories_enabled ON categories(enabled);
CREATE INDEX IF NOT EXISTS idx_kid_schedules_kid_day ON kid_schedules(kid_id, day_of_week);
CREATE INDEX IF NOT EXISTS idx_kid_category_limits_kid ON kid_category_limits(kid_id);
CREATE INDEX IF NOT EXISTS idx_kid_category_limits_category ON kid_category_limits(category_id);
CREATE INDEX IF NOT EXISTS idx_kid_bonus_time_kid_expires_at ON kid_bonus_time(kid_id, expires_at);
CREATE INDEX IF NOT EXISTS idx_search_log_kid_created_at ON search_log(kid_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_watch_log_kid_created_at ON watch_log(kid_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_watch_log_video_created_at ON watch_log(video_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_watch_log_category_created_at ON watch_log(category_id, created_at DESC);

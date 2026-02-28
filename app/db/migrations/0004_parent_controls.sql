ALTER TABLE kids ADD COLUMN pin_hash TEXT;

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    enabled INTEGER NOT NULL DEFAULT 1,
    daily_limit_minutes INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO categories(name, enabled, daily_limit_minutes) VALUES ('education', 1, NULL);
INSERT OR IGNORE INTO categories(name, enabled, daily_limit_minutes) VALUES ('fun', 1, NULL);

ALTER TABLE channels ADD COLUMN category_id INTEGER REFERENCES categories(id);
UPDATE channels SET category_id = (SELECT id FROM categories WHERE name = COALESCE(NULLIF(channels.category, ''), 'fun')) WHERE category_id IS NULL;

CREATE TABLE IF NOT EXISTS kid_category_limits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kid_id INTEGER NOT NULL REFERENCES kids(id),
    category_id INTEGER NOT NULL REFERENCES categories(id),
    daily_limit_minutes INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(kid_id, category_id)
);

CREATE TABLE IF NOT EXISTS kid_schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kid_id INTEGER NOT NULL REFERENCES kids(id),
    day_of_week INTEGER NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS kid_bonus_time (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kid_id INTEGER NOT NULL REFERENCES kids(id),
    minutes INTEGER NOT NULL,
    used_minutes INTEGER NOT NULL DEFAULT 0,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS search_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kid_id INTEGER NOT NULL REFERENCES kids(id),
    query TEXT NOT NULL,
    searched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS video_approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    youtube_id TEXT NOT NULL UNIQUE,
    allowed INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE requests ADD COLUMN payload TEXT;

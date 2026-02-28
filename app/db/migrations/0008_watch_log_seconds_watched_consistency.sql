CREATE TABLE IF NOT EXISTS watch_log_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kid_id INTEGER NOT NULL,
    video_id INTEGER NOT NULL,
    seconds_watched INTEGER NOT NULL,
    category_id INTEGER REFERENCES categories(id),
    started_at TEXT,
    created_at TEXT,
    FOREIGN KEY(kid_id) REFERENCES kids(id),
    FOREIGN KEY(video_id) REFERENCES videos(id)
);

INSERT INTO watch_log_new (
    id,
    kid_id,
    video_id,
    seconds_watched,
    category_id,
    started_at,
    created_at
)
SELECT
    id,
    kid_id,
    video_id,
    COALESCE(seconds_watched, watched_seconds, 0) AS seconds_watched,
    category_id,
    started_at,
    created_at
FROM watch_log;

DROP TABLE watch_log;
ALTER TABLE watch_log_new RENAME TO watch_log;

CREATE INDEX IF NOT EXISTS idx_watch_log_kid_created_at ON watch_log(kid_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_watch_log_video_created_at ON watch_log(video_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_watch_log_category_created_at ON watch_log(category_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_watch_log_kid_category_started_at ON watch_log(kid_id, category_id, started_at DESC);

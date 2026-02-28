CREATE TABLE IF NOT EXISTS requests_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL CHECK(type IN ('video', 'channel', 'bonus')),
    youtube_id TEXT,
    kid_id INTEGER,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'denied')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TEXT,
    FOREIGN KEY(kid_id) REFERENCES kids(id)
);

INSERT INTO requests_new (id, type, youtube_id, kid_id, status, created_at)
SELECT id, type, youtube_id, kid_id, status, created_at
FROM requests;

DROP TABLE requests;
ALTER TABLE requests_new RENAME TO requests;

CREATE TABLE IF NOT EXISTS video_approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    youtube_id TEXT NOT NULL UNIQUE,
    request_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(request_id) REFERENCES requests(id)
);

CREATE INDEX IF NOT EXISTS idx_requests_status_created_at ON requests(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_requests_kid_type ON requests(kid_id, type);

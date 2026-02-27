ALTER TABLE channels ADD COLUMN allowed INTEGER NOT NULL DEFAULT 0;
ALTER TABLE channels ADD COLUMN blocked INTEGER NOT NULL DEFAULT 0;
ALTER TABLE channels ADD COLUMN blocked_at TEXT;
ALTER TABLE channels ADD COLUMN blocked_reason TEXT;

CREATE INDEX IF NOT EXISTS idx_channels_allowed_blocked_enabled ON channels(allowed, blocked, enabled);

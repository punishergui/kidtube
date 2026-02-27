ALTER TABLE channels ADD COLUMN input TEXT;
ALTER TABLE channels ADD COLUMN resolved_at TEXT;
ALTER TABLE channels ADD COLUMN resolve_status TEXT NOT NULL DEFAULT 'pending';
ALTER TABLE channels ADD COLUMN resolve_error TEXT;

CREATE INDEX IF NOT EXISTS idx_channels_enabled ON channels(enabled);
CREATE INDEX IF NOT EXISTS idx_videos_channel_published_at ON videos(channel_id, published_at DESC);

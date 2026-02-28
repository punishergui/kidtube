ALTER TABLE watch_log ADD COLUMN started_at TEXT;
UPDATE watch_log SET started_at = created_at WHERE started_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_watch_log_kid_category_started_at
ON watch_log(kid_id, category_id, started_at DESC);

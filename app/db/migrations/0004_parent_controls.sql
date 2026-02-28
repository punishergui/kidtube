ALTER TABLE kids ADD COLUMN bedtime_start TEXT;
ALTER TABLE kids ADD COLUMN bedtime_end TEXT;
ALTER TABLE kids ADD COLUMN weekend_bonus_minutes INTEGER;
ALTER TABLE kids ADD COLUMN require_parent_approval INTEGER NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_kids_require_parent_approval ON kids(require_parent_approval);

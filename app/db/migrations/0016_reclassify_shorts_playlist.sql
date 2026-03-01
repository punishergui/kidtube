-- Will be re-evaluated on next sync because this migration only resets the 61-180s range
-- Videos that were 61-180s and marked is_short=1 should be rechecked on next sync
-- We cannot definitively fix without re-syncing, so reset misclassified ones
UPDATE videos
SET is_short = 0
WHERE duration_seconds > 60
  AND duration_seconds <= 180
  AND is_short = 1;

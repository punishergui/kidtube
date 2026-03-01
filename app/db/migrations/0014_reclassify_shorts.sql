UPDATE videos SET is_short = 1 WHERE duration_seconds IS NOT NULL AND duration_seconds <= 180 AND is_short = 0;
UPDATE videos SET is_short = 0 WHERE duration_seconds IS NOT NULL AND duration_seconds > 180 AND is_short = 1;

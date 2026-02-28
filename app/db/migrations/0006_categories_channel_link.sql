ALTER TABLE channels ADD COLUMN category_id INTEGER REFERENCES categories(id);

CREATE INDEX IF NOT EXISTS idx_channels_category_id ON channels(category_id);

INSERT OR IGNORE INTO categories (name, enabled)
SELECT 'education', 1;

INSERT OR IGNORE INTO categories (name, enabled)
SELECT 'fun', 1;

UPDATE channels
SET category_id = (
    SELECT id
    FROM categories
    WHERE name = LOWER(TRIM(channels.category))
    LIMIT 1
)
WHERE category_id IS NULL
  AND category IS NOT NULL
  AND TRIM(category) <> '';

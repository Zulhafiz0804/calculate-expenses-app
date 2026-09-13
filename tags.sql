CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    color_hex TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS expense_tags (
    expense_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (expense_id, tag_id),
    FOREIGN KEY (expense_id) REFERENCES expense(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

INSERT INTO tags (name, color_hex)
SELECT '#Food', '#d7ead9'
WHERE NOT EXISTS (SELECT 1 FROM tags WHERE name = '#Food');

INSERT INTO tags (name, color_hex)
SELECT '#Bills', '#cbdcf0'
WHERE NOT EXISTS (SELECT 1 FROM tags WHERE name = '#Bills');

INSERT INTO tags (name, color_hex)
SELECT '#Wants', '#f3d4dc'
WHERE NOT EXISTS (SELECT 1 FROM tags WHERE name = '#Wants');
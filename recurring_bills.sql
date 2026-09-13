CREATE TABLE IF NOT EXISTS recurring_bills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    amount REAL NOT NULL
);

INSERT INTO recurring_bills (category, description, amount)
SELECT 'Bills', 'Internet', 79.99
WHERE NOT EXISTS (SELECT 1 FROM recurring_bills WHERE category = 'Bills' AND description = 'Internet');

INSERT INTO recurring_bills (category, description, amount)
SELECT 'Loan Commitment', 'Car Loan', 310.00
WHERE NOT EXISTS (SELECT 1 FROM recurring_bills WHERE category = 'Loan Commitment' AND description = 'Car Loan');

INSERT INTO recurring_bills (category, description, amount)
SELECT 'Bills', 'Phone Bill', 42.50
WHERE NOT EXISTS (SELECT 1 FROM recurring_bills WHERE category = 'Bills' AND description = 'Phone Bill');

INSERT INTO recurring_bills (category, description, amount)
SELECT 'Bills', 'Electricity', 68.40
WHERE NOT EXISTS (SELECT 1 FROM recurring_bills WHERE category = 'Bills' AND description = 'Electricity');

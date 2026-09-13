# Expense Tracker

A simple mobile-friendly expense tracker built with Python and Flask. It stores daily expenses in SQLite by default and supports PostgreSQL via a `DATABASE_URL` environment variable.

## Project structure

- `app.py` - Flask backend and minimal frontend UI
- `tags.sql` - SQL schema and seed data for custom expense tags
- `requirements.txt` - Python dependencies
- `.env.example` - sample environment settings
- `.gitignore` - standard local ignore file

## Run locally

1. Create a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate   # On Windows: .venv\Scripts\activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Start the app:

   ```bash
   python app.py
   ```

4. Open in the browser:

   ```text
   http://localhost:5000
   ```

## PostgreSQL setup

If you want to use PostgreSQL instead of SQLite, set a database URL before running the app:

```bash
export DATABASE_URL="postgresql://username:password@localhost:5432/expense_tracker"
# or on Windows PowerShell:
$env:DATABASE_URL="postgresql://username:password@localhost:5432/expense_tracker"
```

Then start the app with:

```bash
python app.py
```

The app will automatically create the database tables on startup.

## Custom tags

Run `tags.sql` against an existing database to create the `tags` and `expense_tags` tables and seed `#Food`, `#Bills`, and `#Wants`. The Flask app also creates these tables and seeds the defaults automatically on startup.

The tag API is available at `GET /api/tags` and `POST /api/tags`. Create expenses with `POST /api/expense` (or the existing plural alias) using a JSON `tag_ids` array.

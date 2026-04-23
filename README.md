# ARQA Dashboard

Web app for managing recruitment vacancies, candidates, and pipeline stages.

## Quick Start (development)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000 — runs in mock mode with sample data, no setup needed.

## Architecture

- **PostgreSQL** — primary database (fast reads/writes)
- **Google Sheets** — live mirror, synced automatically in both directions
- **Mock mode** — in-memory sample data for local development

Mode is auto-detected from environment variables. See [DEPLOY.md](DEPLOY.md) for full details.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `FLASK_ENV` | `development` | `development` or `production`. Controls debug mode. |
| `FLASK_SECRET_KEY` | `dev-fallback-key` | Secret key for Flask sessions. |
| `DATABASE_URL` | — | PostgreSQL connection string. Enables Postgres mode. |
| `GOOGLE_SHEET_ID` | — | Google Spreadsheet ID. |
| `GOOGLE_CREDENTIALS_FILE` | `credentials.json` | Path to service account JSON key (local). |
| `GOOGLE_CREDENTIALS_JSON` | — | Inline JSON credentials (deploy). |

## Project Structure

```
app.py              # Flask routes (all API endpoints)
sheets.py           # Storage router (Postgres / Sheets / Mock)
db.py               # PostgreSQL backend
config.py           # Environment config
templates/
  index.html        # Single-page dashboard
static/
  style.css         # All styles
  app.js            # Frontend (state, API, rendering, modals)
```

## Deploy

See [DEPLOY.md](DEPLOY.md) for Google Cloud setup, Render deployment, and collaborator onboarding.

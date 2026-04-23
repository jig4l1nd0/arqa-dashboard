# ARQA Dashboard

Web app for managing recruitment vacancies, candidates, and pipeline stages.

## Getting Started

### 1. Clone or fork

```bash
# If you're forking, click "Fork" on GitHub first, then:
git clone https://github.com/YOUR_USER/arqa-dashboard.git
cd arqa-dashboard
```

### 2. Install dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Run

```bash
python app.py
```

Open **http://127.0.0.1:5000** — the app starts in **mock mode** with sample data. No credentials, no database, no setup needed. You can create, edit, and delete vacantes, candidates, and owners right away.

### 4. Connect to real data (optional)

When you're ready to use real data, create a `.env` file:

```bash
cp .env.example .env
```

Then choose your backend:

**Google Sheets only** (simplest):
```env
GOOGLE_SHEET_ID=your-spreadsheet-id
GOOGLE_CREDENTIALS_FILE=credentials.json
```

**PostgreSQL + Sheets sync** (recommended for teams):
```env
DATABASE_URL=postgresql://localhost/arqa
GOOGLE_SHEET_ID=your-spreadsheet-id
GOOGLE_CREDENTIALS_FILE=credentials.json
```

See [DEPLOY.md](DEPLOY.md) for how to get Google credentials and set up Postgres.

---

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────────┐
│   Browser    │────▶│  Flask App   │────▶│   PostgreSQL     │
│              │◀────│              │◀────│                  │
└─────────────┘     └──────┬───────┘     └──────────────────┘
                           │
                    every 60s push ↓  ↑ every 5min pull
                           │
                    ┌──────▼───────┐
                    │ Google Sheets │
                    └──────────────┘
```

The app auto-detects which mode to run based on what environment variables are set:

| What you configure | Mode | Behavior |
|---|---|---|
| Nothing | **Mock** | In-memory sample data, resets on restart |
| Google credentials | **Sheets** | Reads/writes directly to Google Sheets |
| `DATABASE_URL` + Google credentials | **Postgres** | Fast DB + automatic Sheets sync |

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `FLASK_ENV` | `development` | `development` or `production`. Controls debug mode. |
| `FLASK_SECRET_KEY` | `dev-fallback-key` | Secret key for Flask sessions. |
| `DATABASE_URL` | — | PostgreSQL connection string. Enables Postgres mode. |
| `GOOGLE_SHEET_ID` | — | Google Spreadsheet ID (from the URL). |
| `GOOGLE_CREDENTIALS_FILE` | `credentials.json` | Path to service account JSON key (local dev). |
| `GOOGLE_CREDENTIALS_JSON` | — | Inline JSON credentials (for deploy platforms like Render). |

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

See [DEPLOY.md](DEPLOY.md) for:
- Google Cloud setup (free service account + API keys)
- Render deployment (free Postgres + web service)
- Collaborator onboarding
- Troubleshooting

# ARQA Dashboard

Web app for managing recruitment vacancies, candidates, and pipeline stages — backed by Google Sheets.

## Setup

### 1. Google Cloud Service Account (free)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use an existing one)
3. Enable the **Google Sheets API** and **Google Drive API**:
   - Go to **APIs & Services → Library**
   - Search "Google Sheets API" → Enable
   - Search "Google Drive API" → Enable
4. Create a service account:
   - Go to **APIs & Services → Credentials**
   - Click **Create Credentials → Service account**
   - Name it (e.g. `arqa-dashboard`), click through
5. Create a key:
   - Click on the service account → **Keys** tab
   - **Add Key → Create new key → JSON**
   - Save the downloaded file as `credentials.json` in this project root
6. Share your Google Spreadsheet with the service account email (the `client_email` in the JSON file) — give it **Editor** access

### 2. Environment Variables

```bash
cp .env.example .env
```

Edit `.env`:
- `FLASK_SECRET_KEY`: any random string (e.g. `python3 -c "import secrets; print(secrets.token_hex(32))"`)
- `GOOGLE_SHEET_ID`: the ID from your spreadsheet URL (`https://docs.google.com/spreadsheets/d/<THIS_PART>/edit`)
- `GOOGLE_CREDENTIALS_FILE`: path to your JSON key (default: `credentials.json`)

### 3. Run Locally

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000

### 4. Deploy (free options)

**Render:**
- Push to GitHub, connect repo on [render.com](https://render.com)
- Set build command: `pip install -r requirements.txt`
- Set start command: `gunicorn app:app`
- Add environment variables from `.env`
- For credentials: paste the JSON content as a `GOOGLE_CREDENTIALS_JSON` env var (requires a small code change to load from env instead of file)

**PythonAnywhere:**
- Upload files, set up virtualenv, configure WSGI to point to `app:app`

## Project Structure

```
app.py              # Flask routes (all API endpoints)
sheets.py           # Google Sheets client (gspread wrapper)
config.py           # Environment config
templates/
  index.html        # Single-page dashboard
static/
  style.css         # All styles (ported from Apps Script)
  main.js           # State, API layer, rendering
  modals.js         # Vacancy, candidate, owner modals
```

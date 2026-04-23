# ARQA Dashboard — Deployment & Development Guide

## Architecture Overview

```
┌─────────────┐     ┌──────────────┐     ┌──────────────────┐
│   Browser    │────▶│  Flask App   │────▶│   PostgreSQL     │
│  (10 users)  │◀────│  (Render)    │◀────│   (Render free)  │
└─────────────┘     └──────┬───────┘     └──────────────────┘
                           │
                    every 60s push ↓  ↑ every 5min pull
                           │
                    ┌──────▼───────┐
                    │ Google Sheets │
                    │  (mirror for  │
                    │  manual edits) │
                    └──────────────┘
```

**How it works:**
- The **Flask app** serves the dashboard UI and a REST API
- **PostgreSQL** is the primary database — all reads and writes from the UI go here (sub-millisecond)
- **Google Sheets** is a live mirror, synced automatically:
  - Every **60 seconds**: Postgres → Sheets (so the spreadsheet stays current)
  - Every **5 minutes**: Sheets → Postgres (so manual spreadsheet edits get picked up)
- On first boot with an empty database, the app **auto-imports** all existing data from Google Sheets

**Three runtime modes** (auto-detected from environment variables):

| Env vars present | Mode | Use case |
|---|---|---|
| `DATABASE_URL` + Google creds | **Postgres mode** | Production — fast DB + Sheets sync |
| Google creds only | **Sheets mode** | Lightweight deploy — Sheets as sole backend |
| Nothing | **Mock mode** | Local development — in-memory sample data |

---

## Table of Contents

1. [Google Cloud Setup](#1-google-cloud-setup)
2. [Deploy to Render](#2-deploy-to-render)
3. [Local Development](#3-local-development)
4. [Collaborator Setup](#4-collaborator-setup)
5. [Environment Variables Reference](#5-environment-variables-reference)
6. [Troubleshooting](#6-troubleshooting)

---

## 1. Google Cloud Setup

This is a one-time setup. Everything is free.

### 1.1 Create a Google Cloud project

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Click the **project dropdown** at the top left → **New Project**
3. Name it (e.g. `arqa-dashboard`) → **Create**
4. Make sure the new project is selected in the dropdown

### 1.2 Enable APIs

You need two APIs enabled. Use these direct links (replace `arqa-dashboard` with your project ID if different):

- **Google Sheets API**: https://console.cloud.google.com/apis/api/sheets.googleapis.com?project=arqa-dashboard
- **Google Drive API**: https://console.cloud.google.com/apis/api/drive.googleapis.com?project=arqa-dashboard

Click **Enable** on each page.

Or manually: go to **APIs & Services → Library**, search for each API, and click **Enable**.

> If you just enabled them, wait ~1 minute before starting the app.

### 1.3 Create a Service Account

1. Go to **APIs & Services → Credentials**
2. Click **Create Credentials → Service account**
3. Name: `arqa-dashboard` (anything works)
4. Click **Done** (skip the optional grant steps)
5. You'll see the service account listed — click on it
6. Go to the **Keys** tab
7. Click **Add Key → Create new key → JSON → Create**
8. A `.json` file downloads — this is your `credentials.json`

**Important:** Keep this file safe. It contains the private key for the service account.

### 1.4 Create and share the Google Spreadsheet

1. Go to [Google Sheets](https://sheets.google.com) → create a **new blank spreadsheet**
2. Name it (e.g. "ARQA Dashboard")
3. Copy the **spreadsheet ID** from the URL:
   ```
   https://docs.google.com/spreadsheets/d/COPY_THIS_PART/edit
   ```
   The ID is the long string between `/d/` and `/edit`

4. Open the downloaded `credentials.json` file and find the `client_email` field:
   ```json
   "client_email": "arqa-dashboard@arqa-dashboard.iam.gserviceaccount.com"
   ```

5. In the spreadsheet, click **Share** → paste that email → select **Editor** → **Share**

The app will auto-create the 4 tabs (Vacantes, Candidatos, Aplicaciones, Owners) with headers on first run.

---

## 2. Deploy to Render

### 2.1 Push code to GitHub

1. Create a new repository on [GitHub](https://github.com/new)
2. Push your code:
   ```bash
   cd arqa-dashboard
   git add -A
   git commit -m "Initial commit"
   git remote add origin https://github.com/YOUR_USER/arqa-dashboard.git
   git push -u origin main
   ```

### 2.2 Create a PostgreSQL database on Render

1. Go to [render.com](https://render.com) and sign up (use GitHub for easy repo access)
2. From the dashboard, click **New → PostgreSQL**
3. Configure:
   - **Name:** `arqa-db` (or anything)
   - **Region:** pick the closest to your team
   - **Plan:** **Free**
4. Click **Create Database**
5. Wait for it to be ready, then go to the database page
6. Copy the **Internal Database URL** — it looks like:
   ```
   postgres://arqa_db_user:password@dpg-xxxxx/arqa_db
   ```
   You'll need this in the next step.

### 2.3 Create the Web Service on Render

1. From the Render dashboard, click **New → Web Service**
2. Connect your GitHub repository
3. Configure:
   - **Name:** `arqa-dashboard` (or anything)
   - **Region:** same as your database
   - **Branch:** `main`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
   - **Plan:** **Free**

4. Scroll to **Environment Variables** and add these four:

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | The Internal Database URL from step 2.2 |
   | `FLASK_SECRET_KEY` | A random string (generate with `python3 -c "import secrets; print(secrets.token_hex(32))"`) |
   | `GOOGLE_SHEET_ID` | The spreadsheet ID from step 1.4 |
   | `GOOGLE_CREDENTIALS_JSON` | The **entire contents** of `credentials.json` — open the file, select all, copy, paste |

5. Click **Deploy**

### 2.4 Verify

- Render will build and deploy. First deploy takes ~2 minutes.
- On first boot, the app detects an empty database and **auto-imports all data from Google Sheets**.
- Open the URL Render gives you (e.g. `https://arqa-dashboard.onrender.com`)
- You should see your dashboard with all your data.

### 2.5 Render free tier notes

- The service **sleeps after 15 minutes** of inactivity
- First request after sleep takes **~30 seconds** to wake up
- After that, responses are fast (Postgres queries are sub-millisecond)
- The free Postgres database has a **1GB storage limit** and expires after 90 days (you can recreate it)

---

## 3. Local Development

### 3.1 Quick start (mock mode — no setup needed)

```bash
cd arqa-dashboard
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open **http://127.0.0.1:5000**

The app starts with sample data (3 vacantes, 3 owners, 5 candidates). All changes are in-memory and reset on restart. This is the fastest way to develop and test.

> **macOS note:** Use `127.0.0.1` not `localhost` — macOS AirPlay Receiver sometimes occupies port 5000 on localhost.

### 3.2 With Google Sheets (real data, no Postgres)

1. Place your `credentials.json` in the project root
2. Create a `.env` file:
   ```bash
   cp .env.example .env
   ```
3. Edit `.env`:
   ```
   FLASK_SECRET_KEY=any-random-string
   GOOGLE_SHEET_ID=your-spreadsheet-id
   GOOGLE_CREDENTIALS_FILE=credentials.json
   ```
4. Run:
   ```bash
   python app.py
   ```

This connects directly to Google Sheets. Reads/writes are slower (~1-2s per operation) but you're working with real data.

### 3.3 With local Postgres (full production-like setup)

1. Install and start Postgres locally:
   ```bash
   # macOS with Homebrew
   brew install postgresql@16
   brew services start postgresql@16
   createdb arqa
   ```

2. Add to your `.env`:
   ```
   DATABASE_URL=postgresql://localhost/arqa
   FLASK_SECRET_KEY=any-random-string
   GOOGLE_SHEET_ID=your-spreadsheet-id
   GOOGLE_CREDENTIALS_FILE=credentials.json
   ```

3. Run:
   ```bash
   python app.py
   ```

On first run with an empty DB, it imports from Sheets automatically.

---

## 4. Collaborator Setup

### For a new developer joining the project:

1. **Get added to the GitHub repo** (Settings → Collaborators → Add people)

2. **Clone and run locally:**
   ```bash
   git clone https://github.com/YOUR_USER/arqa-dashboard.git
   cd arqa-dashboard
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   python app.py
   ```
   This runs in **mock mode** — no credentials needed. They get a working app with sample data immediately.

3. **Make changes and push:**
   ```bash
   git checkout -b feature/my-feature
   # ... make changes ...
   git add -A
   git commit -m "feat: description of change"
   git push -u origin feature/my-feature
   ```
   Then create a Pull Request on GitHub.

4. **Render auto-deploys** when changes are merged to `main`.

### What collaborators DON'T need:
- Google Cloud credentials
- PostgreSQL installed locally
- Any environment variables

Mock mode gives them everything they need to develop and test features.

---

## 5. Environment Variables Reference

| Variable | Required | Where | Description |
|---|---|---|---|
| `DATABASE_URL` | Production | Render | PostgreSQL connection string. Activates Postgres mode. |
| `FLASK_SECRET_KEY` | Yes | Everywhere | Secret key for Flask sessions. Any random string. |
| `GOOGLE_SHEET_ID` | For Sheets | Render + local | Spreadsheet ID from the Google Sheets URL. |
| `GOOGLE_CREDENTIALS_FILE` | Local only | Local | Path to the service account JSON key file (default: `credentials.json`). |
| `GOOGLE_CREDENTIALS_JSON` | Deploy only | Render | Full JSON content of the service account key. Use this instead of a file on Render. |

**Priority:** If `DATABASE_URL` is set → Postgres mode. Else if Google creds exist → Sheets mode. Else → Mock mode.

---

## 6. Troubleshooting

### "Google Sheets API has not been used in project..."
Enable the APIs — see [step 1.2](#12-enable-apis). Wait 1 minute after enabling.

### "PermissionError" when connecting to Sheets
Make sure you shared the spreadsheet with the service account email (the `client_email` from `credentials.json`) with **Editor** access.

### App stuck on "Cargando vacantes..."
- Open browser dev console (Cmd+Option+J on Chrome) and check for errors
- Make sure you're using `http://127.0.0.1:5000` not `localhost:5000` on macOS
- Hard refresh with Cmd+Shift+R to clear cached JS

### Render deploy fails
- Check the build logs in the Render dashboard
- Make sure all 4 environment variables are set
- For `GOOGLE_CREDENTIALS_JSON`, paste the **entire** JSON file content (including the curly braces)

### Data not syncing between Sheets and Dashboard
- In Postgres mode: Sheets → DB sync runs every 5 minutes, DB → Sheets every 60 seconds
- Check Render logs for sync errors
- You can trigger an immediate sync: `POST /api/sync-from-sheets`

---

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
Procfile            # Render start command
requirements.txt    # Python dependencies
DEPLOY.md           # This file
```

"""Storage layer — routes to Postgres (primary), Sheets, or mock backend."""

import os
import threading
import time

import gspread
from google.oauth2.service_account import Credentials

# ── Backend state ────────────────────────────────────────────
_backend = None  # "postgres", "sheets", or "mock"
_gspread_client = None
_spreadsheet = None
_mock_data = {}

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ── Sheet schemas (mirrors Schema.gs) ────────────────────────
VACANTES_HEADERS = [
    "ID", "Rol", "Cliente", "OwnerID", "Meta",
    "Status", "Prioridad", "Temperatura",
    "NextSteps", "Notas",
    "FechaCreacion", "FechaActualizacion",
]

CANDIDATOS_HEADERS = [
    "ID", "Nombre", "Email", "Telefono",
    "LinkedIn", "Ciudad", "AnosExperiencia", "ExpectativaSalarial",
    "Fuente", "OriginadorId", "Comentarios",
    "FechaCreacion", "FechaActualizacion", "CV",
]

APLICACIONES_HEADERS = [
    "ID", "CandidatoID", "VacanteID",
    "Lado", "Etapa", "Status",
    "FechaAplicacion", "FechaActualizacion",
]

OWNERS_HEADERS = ["ID", "Nombre", "Color", "FechaCreacion"]

OWNER_COLORS = [
    "teal", "blue", "violet", "pink", "amber",
    "emerald", "rose", "indigo", "orange", "slate",
]

ETAPAS = [
    {"key": "Screening", "label": "Screening", "color": "slate"},
    {"key": "Entrevista ARQA", "label": "Entrevista ARQA", "color": "blue"},
    {"key": "Review Cliente", "label": "Review Cliente", "color": "indigo"},
    {"key": "Entrevista Cliente", "label": "Entrevista Cliente", "color": "violet"},
    {"key": "Pruebas Cliente", "label": "Pruebas Cliente", "color": "amber"},
    {"key": "Offer Letter", "label": "Offer Letter", "color": "teal"},
    {"key": "Hired", "label": "Hired", "color": "emerald"},
    {"key": "Pool ARQA", "label": "Pool ARQA", "color": "slate"},
    {"key": "Pool Cliente", "label": "Pool Cliente", "color": "slate"},
    {"key": "Descartado", "label": "Descartado", "color": "rose"},
]

CANDIDATO_FIELDS = [
    {"key": "nombre", "label": "Nombre completo", "type": "text", "group": "Contacto", "required": True, "placeholder": "Ej. Juan Perez"},
    {"key": "email", "label": "Email", "type": "email", "group": "Contacto", "placeholder": "correo@ejemplo.com"},
    {"key": "telefono", "label": "Telefono", "type": "tel", "group": "Contacto", "placeholder": "+52 55 1234 5678"},
    {"key": "linkedin", "label": "LinkedIn", "type": "url", "group": "Contacto", "placeholder": "linkedin.com/in/usuario"},
    {"key": "ciudad", "label": "Ciudad", "type": "text", "group": "Perfil", "placeholder": "Ej. CDMX"},
    {"key": "anosExperiencia", "label": "Anos de experiencia", "type": "number", "group": "Perfil", "placeholder": "Ej. 5"},
    {"key": "expectativaSalarial", "label": "Expectativa salarial", "type": "text", "group": "Perfil", "placeholder": "Ej. 50-60k MXN mensual"},
    {"key": "fuente", "label": "Fuente", "type": "text", "group": "Perfil", "placeholder": "LinkedIn / Referido / OCC"},
    {"key": "originadorId", "label": "Originador", "type": "owner-select", "group": "Perfil"},
    {"key": "cv", "label": "CV", "type": "url", "group": "Perfil", "placeholder": "https://..."},
    {"key": "comentarios", "label": "Comentarios", "type": "textarea", "group": "Notas", "placeholder": "Notas internas sobre el candidato"},
]

_SHEET_HEADERS = {
    "Vacantes": VACANTES_HEADERS,
    "Candidatos": CANDIDATOS_HEADERS,
    "Aplicaciones": APLICACIONES_HEADERS,
    "Owners": OWNERS_HEADERS,
}


# ── Init ─────────────────────────────────────────────────────
def init_sheets(app):
    global _backend, _gspread_client, _spreadsheet

    database_url = app.config.get("DATABASE_URL", "")
    creds_file = app.config.get("GOOGLE_CREDENTIALS_FILE", "credentials.json")
    sheet_id = app.config.get("GOOGLE_SHEET_ID", "")
    has_sheets = sheet_id and os.path.exists(creds_file)

    # Init Postgres if available
    if database_url:
        import db
        db.init_db(database_url)
        _backend = "postgres"
        print("✅ POSTGRES MODE — primary storage")

        # Init Sheets connection for sync (optional)
        if has_sheets:
            _init_gspread(creds_file, sheet_id)
            print("   + Google Sheets sync enabled")
            # Initial import: if DB is empty, seed from Sheets
            if not db.get_all_rows("Vacantes") and not db.get_all_rows("Owners"):
                print("   → DB empty, importing from Sheets...")
                sync_from_sheets()
            # Start background sync thread
            _start_sync_thread()
        return

    # Sheets-only mode
    if has_sheets:
        _init_gspread(creds_file, sheet_id)
        _backend = "sheets"
        print("📊 SHEETS MODE — using Google Sheets directly")
        return

    # Mock mode
    _backend = "mock"
    print("⚠️  MOCK MODE — no credentials found, using in-memory data")
    _seed_mock_data()


def _init_gspread(creds_file, sheet_id):
    global _gspread_client, _spreadsheet
    creds = Credentials.from_service_account_file(creds_file, scopes=SCOPES)
    _gspread_client = gspread.authorize(creds)
    _spreadsheet = _gspread_client.open_by_key(sheet_id)
    _ensure_gsheets()


def _ensure_gsheets():
    for name, headers in _SHEET_HEADERS.items():
        try:
            ws = _spreadsheet.worksheet(name)
            existing = ws.row_values(1)
            missing = [h for h in headers if h not in existing]
            if missing:
                start_col = len(existing) + 1
                for i, h in enumerate(missing):
                    ws.update_cell(1, start_col + i, h)
        except gspread.exceptions.WorksheetNotFound:
            ws = _spreadsheet.add_worksheet(title=name, rows=1000, cols=len(headers))
            ws.update([headers])
            ws.format("1", {"textFormat": {"bold": True}})


# ── Public API (same interface for all backends) ─────────────
def get_all_rows(sheet_name):
    if _backend == "postgres":
        import db
        return db.get_all_rows(sheet_name)
    if _backend == "mock":
        return [row[:] for row in _mock_data.get(sheet_name, [])]
    data = _spreadsheet.worksheet(sheet_name).get_all_values()
    return data[1:] if len(data) > 1 else []


def find_row_index(sheet_name, col_index, value):
    if _backend == "postgres":
        import db
        return db.find_row_index(sheet_name, col_index, value)
    if _backend == "mock":
        for i, row in enumerate(_mock_data.get(sheet_name, [])):
            if row[col_index] == value:
                return i + 2
        return 0
    data = _spreadsheet.worksheet(sheet_name).get_all_values()
    for i in range(1, len(data)):
        if data[i][col_index] == value:
            return i + 1
    return 0


def append_row(sheet_name, row):
    if _backend == "postgres":
        import db
        db.append_row(sheet_name, row)
        return
    if _backend == "mock":
        _mock_data.setdefault(sheet_name, []).append(row)
        return
    _spreadsheet.worksheet(sheet_name).append_row(row, value_input_option="USER_ENTERED")


def update_cells(sheet_name, row_num, updates):
    if _backend == "postgres":
        import db
        db.update_cells(sheet_name, row_num, updates)
        return
    if _backend == "mock":
        rows = _mock_data.get(sheet_name, [])
        idx = row_num - 2
        if 0 <= idx < len(rows):
            for col_idx, val in updates.items():
                col = int(col_idx)
                while len(rows[idx]) <= col:
                    rows[idx].append("")
                rows[idx][col] = val
        return
    ws = _spreadsheet.worksheet(sheet_name)
    for col_idx, val in updates.items():
        ws.update_cell(row_num, int(col_idx) + 1, val)


def delete_row(sheet_name, row_num):
    if _backend == "postgres":
        import db
        db.delete_row(sheet_name, row_num)
        return
    if _backend == "mock":
        rows = _mock_data.get(sheet_name, [])
        idx = row_num - 2
        if 0 <= idx < len(rows):
            rows.pop(idx)
        return
    _spreadsheet.worksheet(sheet_name).delete_rows(row_num)


# ── Sheets ↔ Postgres sync ──────────────────────────────────
def sync_from_sheets():
    """Pull all data from Google Sheets into Postgres."""
    if _backend != "postgres":
        return {"error": "Sync only available in Postgres mode"}
    if not _spreadsheet:
        return {"error": "Google Sheets not configured"}
    import db
    data = {}
    for name in _SHEET_HEADERS:
        ws_data = _spreadsheet.worksheet(name).get_all_values()
        data[name] = ws_data[1:] if len(ws_data) > 1 else []
    db.import_all(data)
    return {"success": True, "message": "Imported from Sheets"}


def sync_to_sheets():
    """Push all Postgres data to Google Sheets (full replace)."""
    if not _spreadsheet:
        return
    import db
    data = db.export_all()
    for name, headers in _SHEET_HEADERS.items():
        ws = _spreadsheet.worksheet(name)
        ws.clear()
        rows = [headers] + data.get(name, [])
        if rows:
            ws.update(rows, value_input_option="USER_ENTERED")
        ws.format("1", {"textFormat": {"bold": True}})


def _start_sync_thread():
    """Background threads: DB → Sheets every 60s, Sheets → DB every 5min."""
    def _push_loop():
        while True:
            time.sleep(60)
            try:
                sync_to_sheets()
            except Exception as e:
                print(f"⚠️  Sheets push error: {e}")

    def _pull_loop():
        while True:
            time.sleep(300)
            try:
                sync_from_sheets()
            except Exception as e:
                print(f"⚠️  Sheets pull error: {e}")

    threading.Thread(target=_push_loop, daemon=True).start()
    threading.Thread(target=_pull_loop, daemon=True).start()


# ── Mock data ────────────────────────────────────────────────
def _seed_mock_data():
    import json
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    o1, o2, o3 = "owner-1", "owner-2", "owner-3"
    _mock_data["Owners"] = [
        [o1, "Denny", "blue", now],
        [o2, "Fanny", "violet", now],
        [o3, "Tania", "amber", now],
    ]

    c1, c2, c3, c4, c5 = "cand-1", "cand-2", "cand-3", "cand-4", "cand-5"
    _mock_data["Candidatos"] = [
        [c1, "Carlos Martinez", "carlos@example.com", "+52 55 1234 5678", "linkedin.com/in/carlosm", "CDMX", "8", "55-65k MXN", "LinkedIn", o1, "Buen perfil full-stack", now, now, ""],
        [c2, "Ana Lopez", "ana@example.com", "+52 33 9876 5432", "linkedin.com/in/analopez", "GDL", "5", "45-55k MXN", "Referido", o2, "", now, now, ""],
        [c3, "Miguel Torres", "miguel@example.com", "", "", "MTY", "12", "70-80k MXN", "OCC", "", "Senior, busca remoto", now, now, ""],
        [c4, "Laura Rios", "laura@example.com", "+52 55 5555 1234", "linkedin.com/in/laurarios", "CDMX", "3", "35-40k MXN", "LinkedIn", o1, "", now, now, ""],
        [c5, "Pedro Sanchez", "", "", "", "Remoto", "6", "50k MXN", "Referido", o3, "Disponible inmediato", now, now, ""],
    ]

    v1, v2, v3 = "vac-1", "vac-2", "vac-3"
    ns1 = json.dumps([{"t": "Revisar CVs recibidos", "d": True, "f": ""}, {"t": "Agendar entrevistas semana 17", "d": False, "f": ""}])
    ns2 = json.dumps([{"t": "Enviar prueba tecnica", "d": False, "f": ""}])
    _mock_data["Vacantes"] = [
        [v1, "Engineering Manager", "The Palace Company", o1, "3", "activa", "P0", "", ns1, "Cliente busca liderazgo tecnico fuerte", now, now],
        [v2, "Full-Stack Developer", "Acme Corp", o2, "5", "activa", "P1", "", ns2, "React + Node, remoto OK", now, now],
        [v3, "Data Analyst", "StartupXYZ", o3, "2", "inactiva", "P3", "", "", "Pausada por presupuesto del cliente", now, now],
    ]

    _mock_data["Aplicaciones"] = [
        ["app-1", c1, v1, "Cliente", "Entrevista Cliente", "En proceso", now, now],
        ["app-2", c3, v1, "ARQA", "Screening", "En proceso", now, now],
        ["app-3", c2, v2, "ARQA", "Entrevista ARQA", "En proceso", now, now],
        ["app-4", c4, v2, "Cliente", "Review Cliente", "En proceso", now, now],
        ["app-5", c5, v2, "ARQA", "", "En proceso", now, now],
        ["app-6", c3, v3, "ARQA", "Pool ARQA", "En proceso", now, now],
    ]

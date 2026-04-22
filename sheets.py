"""Google Sheets client — thin wrapper around gspread."""

import gspread
from google.oauth2.service_account import Credentials

_client = None
_spreadsheet = None

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


def init_sheets(app):
    """Initialize the gspread client from app config."""
    global _client, _spreadsheet
    creds = Credentials.from_service_account_file(
        app.config["GOOGLE_CREDENTIALS_FILE"], scopes=SCOPES
    )
    _client = gspread.authorize(creds)
    _spreadsheet = _client.open_by_key(app.config["GOOGLE_SHEET_ID"])
    _ensure_sheets()


def _ensure_sheets():
    """Create sheets with headers if they don't exist (idempotent)."""
    for name, headers in [
        ("Vacantes", VACANTES_HEADERS),
        ("Candidatos", CANDIDATOS_HEADERS),
        ("Aplicaciones", APLICACIONES_HEADERS),
        ("Owners", OWNERS_HEADERS),
    ]:
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


def _ws(name):
    return _spreadsheet.worksheet(name)


def get_all_rows(sheet_name):
    """Return all rows except header as list of lists."""
    ws = _ws(sheet_name)
    data = ws.get_all_values()
    return data[1:] if len(data) > 1 else []


def find_row_index(sheet_name, col_index, value):
    """Find 1-based row number (including header) for a value in a column.
    Returns 0 if not found."""
    ws = _ws(sheet_name)
    data = ws.get_all_values()
    for i in range(1, len(data)):
        if data[i][col_index] == value:
            return i + 1  # 1-based for gspread
    return 0


def append_row(sheet_name, row):
    _ws(sheet_name).append_row(row, value_input_option="USER_ENTERED")


def update_cells(sheet_name, row_num, updates):
    """updates: dict of {col_index_0based: value}"""
    ws = _ws(sheet_name)
    for col_idx, val in updates.items():
        ws.update_cell(row_num, int(col_idx) + 1, val)


def delete_row(sheet_name, row_num):
    _ws(sheet_name).delete_rows(row_num)

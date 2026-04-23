"""PostgreSQL storage backend — same interface as sheets.py."""

import psycopg2
import psycopg2.extras

_conn = None


def init_db(database_url):
    global _conn
    _conn = psycopg2.connect(database_url)
    _conn.autocommit = True
    _create_tables()


def _create_tables():
    with _conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS vacantes (
                id TEXT PRIMARY KEY,
                rol TEXT NOT NULL DEFAULT '',
                cliente TEXT NOT NULL DEFAULT '',
                owner_id TEXT NOT NULL DEFAULT '',
                meta INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'activa',
                prioridad TEXT NOT NULL DEFAULT '',
                temperatura TEXT NOT NULL DEFAULT '',
                next_steps TEXT NOT NULL DEFAULT '',
                notas TEXT NOT NULL DEFAULT '',
                fecha_creacion TEXT NOT NULL DEFAULT '',
                fecha_actualizacion TEXT NOT NULL DEFAULT ''
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS candidatos (
                id TEXT PRIMARY KEY,
                nombre TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT '',
                telefono TEXT NOT NULL DEFAULT '',
                linkedin TEXT NOT NULL DEFAULT '',
                ciudad TEXT NOT NULL DEFAULT '',
                anos_experiencia TEXT NOT NULL DEFAULT '',
                expectativa_salarial TEXT NOT NULL DEFAULT '',
                fuente TEXT NOT NULL DEFAULT '',
                originador_id TEXT NOT NULL DEFAULT '',
                comentarios TEXT NOT NULL DEFAULT '',
                fecha_creacion TEXT NOT NULL DEFAULT '',
                fecha_actualizacion TEXT NOT NULL DEFAULT '',
                cv TEXT NOT NULL DEFAULT ''
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS aplicaciones (
                id TEXT PRIMARY KEY,
                candidato_id TEXT NOT NULL DEFAULT '',
                vacante_id TEXT NOT NULL DEFAULT '',
                lado TEXT NOT NULL DEFAULT 'ARQA',
                etapa TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'En proceso',
                fecha_aplicacion TEXT NOT NULL DEFAULT '',
                fecha_actualizacion TEXT NOT NULL DEFAULT ''
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS owners (
                id TEXT PRIMARY KEY,
                nombre TEXT NOT NULL DEFAULT '',
                color TEXT NOT NULL DEFAULT 'slate',
                fecha_creacion TEXT NOT NULL DEFAULT ''
            )
        """)


# ── Column mappings (sheet col index → db column name) ───────
_TABLE_COLS = {
    "Vacantes": [
        "id", "rol", "cliente", "owner_id", "meta", "status",
        "prioridad", "temperatura", "next_steps", "notas",
        "fecha_creacion", "fecha_actualizacion",
    ],
    "Candidatos": [
        "id", "nombre", "email", "telefono", "linkedin", "ciudad",
        "anos_experiencia", "expectativa_salarial", "fuente",
        "originador_id", "comentarios", "fecha_creacion",
        "fecha_actualizacion", "cv",
    ],
    "Aplicaciones": [
        "id", "candidato_id", "vacante_id", "lado", "etapa",
        "status", "fecha_aplicacion", "fecha_actualizacion",
    ],
    "Owners": ["id", "nombre", "color", "fecha_creacion"],
}

_TABLE_NAME = {
    "Vacantes": "vacantes",
    "Candidatos": "candidatos",
    "Aplicaciones": "aplicaciones",
    "Owners": "owners",
}


def get_all_rows(sheet_name):
    table = _TABLE_NAME[sheet_name]
    cols = _TABLE_COLS[sheet_name]
    with _conn.cursor() as cur:
        cur.execute(f"SELECT {','.join(cols)} FROM {table}")
        rows = cur.fetchall()
    return [list(str(v) if v is not None else "" for v in row) for row in rows]


def find_row_index(sheet_name, col_index, value):
    table = _TABLE_NAME[sheet_name]
    cols = _TABLE_COLS[sheet_name]
    col_name = cols[col_index]
    with _conn.cursor() as cur:
        cur.execute(f"SELECT id FROM {table} WHERE {col_name} = %s LIMIT 1", (value,))
        row = cur.fetchone()
    # Return a truthy value (the id) or 0 — callers just check truthiness
    return row[0] if row else 0


def append_row(sheet_name, row):
    table = _TABLE_NAME[sheet_name]
    cols = _TABLE_COLS[sheet_name]
    # Pad row if shorter than cols
    padded = list(row) + [""] * (len(cols) - len(row))
    placeholders = ",".join(["%s"] * len(cols))
    with _conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})",
            [str(v) for v in padded[:len(cols)]],
        )


def update_cells(sheet_name, row_num, updates):
    """updates: dict of {col_index_0based: value}.
    row_num here is actually the row ID (from find_row_index)."""
    table = _TABLE_NAME[sheet_name]
    cols = _TABLE_COLS[sheet_name]
    sets = []
    vals = []
    for col_idx, val in updates.items():
        col_name = cols[int(col_idx)]
        sets.append(f"{col_name} = %s")
        vals.append(str(val))
    if not sets:
        return
    # row_num is the id value from find_row_index
    vals.append(str(row_num))
    with _conn.cursor() as cur:
        cur.execute(f"UPDATE {table} SET {','.join(sets)} WHERE id = %s", vals)


def delete_row(sheet_name, row_num):
    """row_num is the id value from find_row_index."""
    table = _TABLE_NAME[sheet_name]
    with _conn.cursor() as cur:
        cur.execute(f"DELETE FROM {table} WHERE id = %s", (str(row_num),))


# ── Sync helpers ─────────────────────────────────────────────
def export_all():
    """Return all data as dict of sheet_name → list of rows."""
    result = {}
    for sheet_name in _TABLE_COLS:
        result[sheet_name] = get_all_rows(sheet_name)
    return result


def import_all(data):
    """Replace all DB data with data from sheets.
    data: dict of sheet_name → list of rows."""
    for sheet_name, rows in data.items():
        table = _TABLE_NAME[sheet_name]
        cols = _TABLE_COLS[sheet_name]
        with _conn.cursor() as cur:
            cur.execute(f"DELETE FROM {table}")
            for row in rows:
                padded = list(row) + [""] * (len(cols) - len(row))
                placeholders = ",".join(["%s"] * len(cols))
                cur.execute(
                    f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})",
                    [str(v) for v in padded[:len(cols)]],
                )

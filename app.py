"""ARQA Dashboard — Flask application."""

import json
import re
import traceback
import uuid
from datetime import datetime

from flask import Flask, jsonify, render_template, request

import sheets
from config import Config

app = Flask(__name__)
app.config.from_object(Config)


@app.errorhandler(Exception)
def handle_error(e):
    traceback.print_exc()
    return jsonify({"error": str(e)}), 500

# ── Column index maps (mirrors Schema.gs) ────────────────────
V_ID, V_ROL, V_CLIENTE, V_OWNER, V_META = 0, 1, 2, 3, 4
V_STATUS, V_PRIO, V_TEMP, V_NEXT, V_NOTAS = 5, 6, 7, 8, 9
V_CREATED, V_UPDATED = 10, 11

C_ID, C_NOMBRE, C_EMAIL, C_TEL = 0, 1, 2, 3
C_LINKEDIN, C_CIUDAD, C_ANOS, C_SALARIO = 4, 5, 6, 7
C_FUENTE, C_ORIG, C_COMENTARIOS = 8, 9, 10
C_CREATED, C_UPDATED, C_CV = 11, 12, 13

A_ID, A_CAND, A_VAC, A_LADO, A_ETAPA, A_STATUS = 0, 1, 2, 3, 4, 5
A_FECHA_APP, A_UPDATED = 6, 7

O_ID, O_NOMBRE, O_COLOR, O_CREATED = 0, 1, 2, 3


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _uid():
    return str(uuid.uuid4())


def _safe(row, idx):
    return row[idx] if idx < len(row) else ""


# ── Helpers ──────────────────────────────────────────────────
def _parse_next_steps(raw):
    if not raw:
        return []
    raw = str(raw).strip()
    if raw.startswith("["):
        try:
            arr = json.loads(raw)
            if isinstance(arr, list):
                return [
                    {"t": str(i.get("t", "")).strip(), "d": bool(i.get("d")), "f": str(i.get("f", ""))}
                    for i in arr[:5] if str(i.get("t", "")).strip()
                ]
        except (json.JSONDecodeError, AttributeError):
            pass
    return [{"t": raw, "d": False, "f": ""}] if raw else []


def _serialize_next_steps(arr):
    if not arr:
        return ""
    clean = [
        {"t": str(s.get("t", "")).strip(), "d": bool(s.get("d")), "f": str(s.get("f", "")).strip()}
        for s in arr[:5] if str(s.get("t", "")).strip()
    ]
    return json.dumps(clean) if clean else ""


def _get_owners():
    rows = sheets.get_all_rows("Owners")
    return [
        {"id": r[O_ID], "nombre": r[O_NOMBRE] or "", "color": r[O_COLOR] or "slate"}
        for r in rows if r[O_ID]
    ]


def _get_candidatos():
    rows = sheets.get_all_rows("Candidatos")
    return [_row_to_candidato(r) for r in rows if r[C_ID]]


def _row_to_candidato(r):
    return {
        "id": r[C_ID],
        "nombre": _safe(r, C_NOMBRE) or "",
        "email": _safe(r, C_EMAIL) or "",
        "telefono": _safe(r, C_TEL) or "",
        "linkedin": _safe(r, C_LINKEDIN) or "",
        "ciudad": _safe(r, C_CIUDAD) or "",
        "anosExperiencia": _safe(r, C_ANOS) or "",
        "expectativaSalarial": _safe(r, C_SALARIO) or "",
        "fuente": _safe(r, C_FUENTE) or "",
        "originadorId": _safe(r, C_ORIG) or "",
        "cv": _safe(r, C_CV) or "",
        "comentarios": _safe(r, C_COMENTARIOS) or "",
    }


def _get_aplicaciones():
    rows = sheets.get_all_rows("Aplicaciones")
    return [
        {
            "id": r[A_ID],
            "candidatoId": r[A_CAND] or "",
            "vacanteId": r[A_VAC] or "",
            "lado": r[A_LADO] or "ARQA",
            "etapa": _safe(r, A_ETAPA) or "",
            "status": _safe(r, A_STATUS) or "En proceso",
        }
        for r in rows if r[A_ID]
    ]


def _get_apps_by_vacante(vacante_id, cands_by_id):
    apps = [a for a in _get_aplicaciones() if a["vacanteId"] == vacante_id]
    return [
        {
            "id": a["id"],
            "candidatoId": a["candidatoId"],
            "nombre": cands_by_id[a["candidatoId"]]["nombre"]
            if a["candidatoId"] in cands_by_id else "(candidato eliminado)",
            "lado": a["lado"],
            "status": a["status"],
            "etapa": a["etapa"],
        }
        for a in apps
    ]


def _delete_apps_by_vacante(vacante_id):
    rows = sheets.get_all_rows("Aplicaciones")
    for i in range(len(rows) - 1, -1, -1):
        if rows[i][A_VAC] == vacante_id:
            row_ref = sheets.find_row_index("Aplicaciones", A_ID, rows[i][A_ID])
            if row_ref:
                sheets.delete_row("Aplicaciones", row_ref)


def _delete_apps_by_candidato(candidato_id):
    rows = sheets.get_all_rows("Aplicaciones")
    for i in range(len(rows) - 1, -1, -1):
        if rows[i][A_CAND] == candidato_id:
            row_ref = sheets.find_row_index("Aplicaciones", A_ID, rows[i][A_ID])
            if row_ref:
                sheets.delete_row("Aplicaciones", row_ref)


# ── Validation ───────────────────────────────────────────────
def _validate_vacante(data):
    errs = []
    if not data:
        return ["data vacio"]
    if not (data.get("rol") or "").strip():
        errs.append("rol requerido")
    if not (data.get("cliente") or "").strip():
        errs.append("cliente requerido")
    if not data.get("ownerId"):
        errs.append("owner requerido")
    try:
        meta = int(data.get("meta", 0))
        if meta < 1:
            errs.append("meta invalida")
    except (ValueError, TypeError):
        errs.append("meta invalida")
    if data.get("status") and data["status"] not in ("activa", "inactiva"):
        errs.append("status invalido")
    if data.get("prioridad") and not re.match(r"^P[0-4]$", data["prioridad"]):
        errs.append("prioridad invalida")
    return errs


def _validate_candidato(data):
    errs = []
    if not data:
        return ["data vacio"]
    if "nombre" in data and not str(data["nombre"]).strip():
        errs.append("nombre no puede estar vacio")
    email = str(data.get("email", "")).strip()
    if email and not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
        errs.append("email con formato invalido")
    anos = data.get("anosExperiencia", "")
    if anos != "" and anos is not None:
        try:
            n = float(anos)
            if n < 0 or n > 70:
                errs.append("anos de experiencia invalidos")
        except (ValueError, TypeError):
            errs.append("anos de experiencia invalidos")
    return errs


def _validate_owner(data):
    errs = []
    if not data:
        return ["data vacio"]
    if not (data.get("nombre") or "").strip():
        errs.append("nombre requerido")
    if not data.get("color"):
        errs.append("color requerido")
    if data.get("color") and data["color"] not in sheets.OWNER_COLORS:
        errs.append("color invalido: " + data["color"])
    if data.get("nombre") and len(str(data["nombre"]).strip()) > 40:
        errs.append("nombre muy largo (max 40)")
    return errs


# ── Routes ───────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/data")
def get_data():
    """Main dashboard payload — replaces getData() in Apps Script."""
    candidatos = _get_candidatos()
    cands_by_id = {c["id"]: c for c in candidatos}

    v_rows = sheets.get_all_rows("Vacantes")
    vacantes = []
    for r in v_rows:
        if not r[V_ID]:
            continue
        vid = r[V_ID]
        vacantes.append({
            "id": vid,
            "rol": r[V_ROL] or "",
            "cliente": r[V_CLIENTE] or "",
            "ownerId": r[V_OWNER] or "",
            "meta": int(r[V_META]) if r[V_META] else 0,
            "status": r[V_STATUS] or "activa",
            "prioridad": r[V_PRIO] or "",
            "temperatura": _safe(r, V_TEMP) or "",
            "nextSteps": _parse_next_steps(_safe(r, V_NEXT)),
            "notas": _safe(r, V_NOTAS) or "",
            "candidatos": _get_apps_by_vacante(vid, cands_by_id),
        })

    return jsonify({
        "vacantes": vacantes,
        "owners": _get_owners(),
        "candidatoFields": sheets.CANDIDATO_FIELDS,
        "etapas": sheets.ETAPAS,
    })


@app.route("/api/vacante", methods=["POST"])
def save_vacante():
    data = request.get_json()
    errs = _validate_vacante(data)
    if errs:
        return jsonify({"error": ", ".join(errs)}), 400

    now = _now()
    vid = data.get("id")
    ns_json = _serialize_next_steps(data.get("nextSteps", []))
    previous_cand_ids = []

    if vid:
        row_num = sheets.find_row_index("Vacantes", V_ID, vid)
        if not row_num:
            return jsonify({"error": "Vacante no encontrada"}), 404
        sheets.update_cells("Vacantes", row_num, {
            V_ROL: data["rol"], V_CLIENTE: data["cliente"],
            V_OWNER: data["ownerId"], V_META: data["meta"],
            V_STATUS: data.get("status", "activa"),
            V_PRIO: data.get("prioridad", ""),
            V_TEMP: data.get("temperatura", ""),
            V_NEXT: ns_json, V_NOTAS: data.get("notas", ""),
            V_UPDATED: now,
        })
        existing_apps = [a for a in _get_aplicaciones() if a["vacanteId"] == vid]
        previous_cand_ids = [a["candidatoId"] for a in existing_apps]
        _delete_apps_by_vacante(vid)
    else:
        vid = _uid()
        sheets.append_row("Vacantes", [
            vid, data["rol"], data["cliente"], data["ownerId"],
            data["meta"], data.get("status", "activa"),
            data.get("prioridad", ""), data.get("temperatura", ""),
            ns_json, data.get("notas", ""), now, now,
        ])

    # Index previous candidates by name for reuse
    prev_cands_by_name = {}
    if previous_cand_ids:
        all_cands = _get_candidatos()
        for c in all_cands:
            if c["id"] in previous_cand_ids:
                prev_cands_by_name[c["nombre"].strip().lower()] = c["id"]

    reused_ids = []
    for c in data.get("candidatos", []):
        nombre = (c.get("nombre") or "").strip()
        if not nombre:
            continue
        key = nombre.lower()
        if key in prev_cands_by_name:
            cand_id = prev_cands_by_name[key]
            reused_ids.append(cand_id)
        else:
            cand_id = _uid()
            sheets.append_row("Candidatos", [
                cand_id, nombre, "", "", "", "", "", "", "", "", "",
                now, now, "",
            ])
        sheets.append_row("Aplicaciones", [
            _uid(), cand_id, vid,
            c.get("lado", "ARQA"), "", c.get("status", "En proceso"),
            now, now,
        ])

    # Clean orphans
    for prev_id in previous_cand_ids:
        if prev_id in reused_ids:
            continue
        still_used = any(
            a["candidatoId"] == prev_id for a in _get_aplicaciones()
        )
        if not still_used:
            row_num = sheets.find_row_index("Candidatos", C_ID, prev_id)
            if row_num:
                sheets.delete_row("Candidatos", row_num)

    return jsonify({"success": True, "id": vid})


@app.route("/api/vacante/<vacante_id>", methods=["DELETE"])
def delete_vacante(vacante_id):
    row_num = sheets.find_row_index("Vacantes", V_ID, vacante_id)
    if not row_num:
        return jsonify({"error": "Vacante no encontrada"}), 404
    sheets.delete_row("Vacantes", row_num)
    _delete_apps_by_vacante(vacante_id)
    return jsonify({"success": True})


@app.route("/api/vacante/<vacante_id>/status", methods=["PATCH"])
def update_status(vacante_id):
    data = request.get_json()
    new_status = data.get("status")
    if new_status not in ("activa", "inactiva"):
        return jsonify({"error": "Status invalido"}), 400
    row_num = sheets.find_row_index("Vacantes", V_ID, vacante_id)
    if not row_num:
        return jsonify({"error": "Vacante no encontrada"}), 404
    sheets.update_cells("Vacantes", row_num, {V_STATUS: new_status, V_UPDATED: _now()})
    return jsonify({"success": True})


# ── Candidato profile ────────────────────────────────────────
@app.route("/api/candidato-profile/<aplicacion_id>")
def get_candidato_profile(aplicacion_id):
    apps = _get_aplicaciones()
    app_obj = next((a for a in apps if a["id"] == aplicacion_id), None)
    if not app_obj:
        return jsonify({"error": "Aplicacion no encontrada"}), 404

    rows = sheets.get_all_rows("Candidatos")
    cand = None
    for r in rows:
        if r[C_ID] == app_obj["candidatoId"]:
            cand = _row_to_candidato(r)
            break
    if not cand:
        return jsonify({"error": "Candidato no encontrado"}), 404

    return jsonify({
        "candidato": cand,
        "aplicacion": app_obj,
        "aplicacionId": aplicacion_id,
    })


@app.route("/api/candidato-profile", methods=["POST"])
def save_candidato_profile():
    data = request.get_json()
    apl_id = data.get("aplicacionId")
    cand_id = data.get("candidatoId")
    if not apl_id or not cand_id:
        return jsonify({"error": "aplicacionId y candidatoId requeridos"}), 400

    cand_data = data.get("candidato", {})
    if cand_data:
        errs = _validate_candidato(cand_data)
        if errs:
            return jsonify({"error": ", ".join(errs)}), 400
        row_num = sheets.find_row_index("Candidatos", C_ID, cand_id)
        if not row_num:
            return jsonify({"error": "Candidato no encontrado"}), 404
        updates = {}
        field_map = {
            "nombre": C_NOMBRE, "email": C_EMAIL, "telefono": C_TEL,
            "linkedin": C_LINKEDIN, "ciudad": C_CIUDAD,
            "anosExperiencia": C_ANOS, "expectativaSalarial": C_SALARIO,
            "fuente": C_FUENTE, "originadorId": C_ORIG,
            "cv": C_CV, "comentarios": C_COMENTARIOS,
        }
        for key, col in field_map.items():
            if key in cand_data:
                updates[col] = str(cand_data[key]).strip()
        updates[C_UPDATED] = _now()
        sheets.update_cells("Candidatos", row_num, updates)

    app_data = data.get("aplicacion", {})
    if app_data:
        apl_row = sheets.find_row_index("Aplicaciones", A_ID, apl_id)
        if apl_row:
            apl_updates = {}
            if "lado" in app_data:
                apl_updates[A_LADO] = app_data["lado"]
            if "etapa" in app_data:
                apl_updates[A_ETAPA] = app_data["etapa"]
            apl_updates[A_UPDATED] = _now()
            sheets.update_cells("Aplicaciones", apl_row, apl_updates)

    return jsonify({"success": True})


@app.route("/api/candidato/<aplicacion_id>", methods=["DELETE"])
def delete_candidato(aplicacion_id):
    apps = _get_aplicaciones()
    app_obj = next((a for a in apps if a["id"] == aplicacion_id), None)
    if not app_obj:
        return jsonify({"error": "Aplicacion no encontrada"}), 404

    cand_id = app_obj["candidatoId"]
    apl_row = sheets.find_row_index("Aplicaciones", A_ID, aplicacion_id)
    if apl_row:
        sheets.delete_row("Aplicaciones", apl_row)

    remaining = [
        r for r in sheets.get_all_rows("Aplicaciones")
        if r[A_CAND] == cand_id
    ]
    if not remaining:
        cand_row = sheets.find_row_index("Candidatos", C_ID, cand_id)
        if cand_row:
            _delete_apps_by_candidato(cand_id)
            sheets.delete_row("Candidatos", cand_row)

    return jsonify({"success": True})


# ── Owners ───────────────────────────────────────────────────
@app.route("/api/owner", methods=["POST"])
def save_owner():
    data = request.get_json()
    errs = _validate_owner(data)
    if errs:
        return jsonify({"error": ", ".join(errs)}), 400

    oid = data.get("id")
    now = _now()

    if oid:
        row_num = sheets.find_row_index("Owners", O_ID, oid)
        if not row_num:
            return jsonify({"error": "Owner no encontrado"}), 404
        sheets.update_cells("Owners", row_num, {
            O_NOMBRE: data["nombre"].strip(),
            O_COLOR: data["color"],
        })
    else:
        oid = _uid()
        sheets.append_row("Owners", [oid, data["nombre"].strip(), data["color"], now])

    return jsonify({"success": True, "id": oid})


@app.route("/api/owner/<owner_id>", methods=["DELETE"])
def delete_owner(owner_id):
    v_rows = sheets.get_all_rows("Vacantes")
    count = sum(1 for r in v_rows if r[V_OWNER] == owner_id)
    if count:
        return jsonify({
            "error": f"No se puede eliminar: tiene {count} vacante{'s' if count != 1 else ''} asignada{'s' if count != 1 else ''}. Reasigna primero."
        }), 400

    row_num = sheets.find_row_index("Owners", O_ID, owner_id)
    if not row_num:
        return jsonify({"error": "Owner no encontrado"}), 404
    sheets.delete_row("Owners", row_num)
    return jsonify({"success": True})


# ── Sync ─────────────────────────────────────────────────────
@app.route("/api/sync-from-sheets", methods=["POST"])
def sync_from_sheets():
    result = sheets.sync_from_sheets()
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)


# ── App init ─────────────────────────────────────────────────
with app.app_context():
    sheets.init_sheets(app)

if __name__ == "__main__":
    app.run(debug=app.config["DEBUG"], port=5000)

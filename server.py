"""FastAPI backend: grades + turmas (persistidos em SQLite).

Turma model:
  { id, grade_id, label, start_year, start_bim, source }
Global config:
  { current_bimestre: { year, bim } }
Module of turma = (year_now - year_start) * 4 + (bim_now - bim_start) + 1
"""
from __future__ import annotations
import unicodedata
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import db as _db
from agenda_loader import derive_turmas, parse_agenda
from calendar_data import all_periods, bim_info
from config import (
    AGENDA_PATH,
    STATIC_DIR,
)
from loader_sql import Discipline, Grade, load_grades_sql, load_canonical_sql


app = FastAPI(title="Grade Timeline")

_cache: dict = {}

_db.init_db()


@app.on_event("startup")
def _warm_cache() -> None:
    """Parse xlsx once at boot so first request is fast."""
    _load()


def _fold(s: str) -> str:
    return (
        unicodedata.normalize("NFKD", s or "")
        .encode("ascii", "ignore")
        .decode()
        .lower()
        .strip()
    )


def _module_key(m):
    return (1, m) if isinstance(m, int) else (0, str(m))


def _canonical_for(d: Discipline, db: CanonicalDB) -> str:
    return db.canonical_for(d.codigo, d.nome or d.codigo)


def _load() -> tuple[list[Grade], object]:
    if "grades" not in _cache:
        _cache["grades"] = load_grades_sql()
        _cache["db"] = load_canonical_sql()
    return _cache["grades"], _cache["db"]


def _bim_index(year: int, bim: int) -> int:
    return year * 4 + (bim - 1)


def _from_bim_index(idx: int) -> tuple[int, int]:
    return idx // 4, (idx % 4) + 1


def _module_for_turma(turma: dict, current_bim: dict) -> int:
    """Compute current module from start (year, bim) + current bim."""
    return (
        _bim_index(current_bim["year"], current_bim["bim"])
        - _bim_index(turma["start_year"], turma["start_bim"])
        + 1
    )


def _load_state() -> dict:
    """Read fresh from SQLite each call (so external edits are picked up)."""
    return {
        "current_bimestre": _db.get_config(),
        "turmas": _db.list_turmas(),
    }


def _serialize_turma(t: dict, current_bim: dict, max_mod: int | None = None) -> dict:
    mod = _module_for_turma(t, current_bim)
    graduated = max_mod is not None and mod > max_mod
    return {
        "id": t["id"],
        "grade_id": t["grade_id"],
        "label": t["label"],
        "start_year": t["start_year"],
        "start_bim": t["start_bim"],
        "current_module": mod,
        "graduated": graduated,
        "source": t.get("source", "manual"),
    }


def _serialize_discipline(d: Discipline, db: CanonicalDB) -> dict:
    return {
        "codigo": d.codigo,
        "nome": d.nome,
        "canonical": _canonical_for(d, db),
        "ch_teo": d.ch_teo,
        "ch_pra": d.ch_pra,
        "ch_ext": d.ch_ext,
        "ch_total": d.ch_total,
        "modulo": d.modulo,
        "grade_id": d.grade_id,
        "ementa": db.ementa_for(d.codigo),
    }


def _attach_turmas(offering: dict, turmas_by_grade: dict, current_bim: dict) -> None:
    """Attach turma_deltas per grade."""
    result = []
    for t in turmas_by_grade.get(offering["grade_id"], []):
        mod = _module_for_turma(t, current_bim)
        delta = None
        if isinstance(offering["modulo"], int):
            delta = offering["modulo"] - mod
        result.append(
            {
                "turma_id": t["id"],
                "label": t["label"],
                "current_module": mod,
                "delta": delta,
            }
        )
    offering["turma_deltas"] = result


def _grade_max_mod(grades: list[Grade]) -> dict[str, int]:
    out = {}
    for g in grades:
        ints = [m for m in g.modules if isinstance(m, int)]
        out[g.id] = max(ints) if ints else 0
    return out


@app.get("/api/calendar")
def api_calendar() -> dict:
    return {"periods": all_periods()}


@app.get("/api/config")
def api_get_config() -> dict:
    state = _load_state()
    return {"current_bimestre": state["current_bimestre"]}


@app.post("/api/config")
def api_set_config(payload: dict) -> dict:
    cb = payload.get("current_bimestre") or {}
    try:
        year = int(cb.get("year"))
        bim = int(cb.get("bim"))
    except (TypeError, ValueError):
        raise HTTPException(400, "current_bimestre {year, bim} required (ints)")
    if bim not in (1, 2, 3, 4):
        raise HTTPException(400, "bim must be 1-4")
    _db.set_config(year, bim)
    return {"current_bimestre": _db.get_config()}


@app.get("/api/grades")
def api_grades() -> dict:
    grades, db = _load()
    result = []
    for g in grades:
        mods_sorted = sorted(g.modules.keys(), key=_module_key)
        result.append(
            {
                "id": g.id,
                "nome_completo": g.nome_completo,
                "modules": [str(m) for m in mods_sorted],
                "num_modules": len(mods_sorted),
                "total_disciplines": sum(len(x) for x in g.modules.values()),
            }
        )
    return {"grades": result}


@app.get("/api/turmas")
def api_turmas() -> dict:
    grades, _ = _load()
    max_mod = _grade_max_mod(grades)
    state = _load_state()
    cur = state["current_bimestre"]
    return {
        "current_bimestre": cur,
        "turmas": [_serialize_turma(t, cur, max_mod.get(t["grade_id"])) for t in state["turmas"]],
    }


@app.post("/api/turmas")
def api_turma_create(payload: dict) -> dict:
    grade_id = payload.get("grade_id")
    if not grade_id:
        raise HTTPException(400, "grade_id required")
    grades, _ = _load()
    if grade_id not in {g.id for g in grades}:
        raise HTTPException(400, f"grade {grade_id} not loaded")
    cur = _db.get_config()
    try:
        sy = int(payload.get("start_year", cur["year"]))
        sb = int(payload.get("start_bim", cur["bim"]))
    except (TypeError, ValueError):
        raise HTTPException(400, "start_year and start_bim must be integers")
    if sb not in (1, 2, 3, 4):
        raise HTTPException(400, "start_bim must be 1-4")
    turma = {
        "id": str(uuid.uuid4())[:8],
        "grade_id": grade_id,
        "label": payload.get("label") or f"Turma {sy}",
        "start_year": sy,
        "start_bim": sb,
        "source": "manual",
    }
    _db.create_turma(turma)
    max_mod = _grade_max_mod(grades)
    return {"turma": _serialize_turma(turma, cur, max_mod.get(grade_id))}


@app.patch("/api/turmas/{turma_id}")
def api_turma_update(turma_id: str, payload: dict) -> dict:
    updates: dict = {}
    if "label" in payload:
        updates["label"] = payload["label"]
    if "start_year" in payload:
        try:
            updates["start_year"] = int(payload["start_year"])
        except (TypeError, ValueError):
            raise HTTPException(400, "start_year must be int")
    if "start_bim" in payload:
        try:
            sb = int(payload["start_bim"])
        except (TypeError, ValueError):
            raise HTTPException(400, "start_bim must be int")
        if sb not in (1, 2, 3, 4):
            raise HTTPException(400, "start_bim must be 1-4")
        updates["start_bim"] = sb
    t = _db.update_turma(turma_id, updates)
    if t is None:
        raise HTTPException(404, "turma not found")
    grades, _ = _load()
    max_mod = _grade_max_mod(grades)
    return {"turma": _serialize_turma(t, _db.get_config(), max_mod.get(t["grade_id"]))}


@app.delete("/api/turmas/{turma_id}")
def api_turma_delete(turma_id: str) -> dict:
    ok = _db.delete_turma(turma_id)
    if not ok:
        raise HTTPException(404, "turma not found")
    return {"ok": True}


@app.post("/api/turmas/bootstrap")
def api_turmas_bootstrap(payload: dict = None) -> dict:
    """Populate turmas from Agenda. start_bim = 1 of turma_year.
    Sets current_bimestre = 2026-2 (agenda captures up to M2 2026).
    """
    payload = payload or {}
    if not AGENDA_PATH.exists():
        raise HTTPException(400, f"agenda not found: {AGENDA_PATH}")
    entries = parse_agenda(str(AGENDA_PATH))
    derived = derive_turmas(entries, str(GRADES_DIR))
    grades, _ = _load()
    valid_grade_ids = {g.id for g in grades}

    # Agenda 2026 captures data up to Módulo II 2026. Set bim atual = 2026-2.
    ANCHOR = {"year": 2026, "bim": 2}
    if payload.get("replace"):
        # Only wipe agenda-sourced rows; keep manual turmas intact.
        _db.clear_turmas(only_source="agenda2026")
        _db.set_config(ANCHOR["year"], ANCHOR["bim"])
    anchor_idx = _bim_index(ANCHOR["year"], ANCHOR["bim"])

    existing = {(t["grade_id"], t.get("label", "")) for t in _db.list_turmas()}
    added = 0
    for d in derived:
        if d["missing_grade"] or d["grade_id"] not in valid_grade_ids:
            continue
        label = f"Turma {d['turma_year']}"
        if (d["grade_id"], label) in existing:
            continue
        # Compute start from the module the turma is currently AT (from agenda).
        # start_idx = anchor_idx - current_module + 1
        try:
            cur_mod = int(d["current_module"])
        except (TypeError, ValueError):
            cur_mod = 1
        start_idx = anchor_idx - cur_mod + 1
        sy, sb = _from_bim_index(start_idx)
        _db.create_turma(
            {
                "id": str(uuid.uuid4())[:8],
                "grade_id": d["grade_id"],
                "label": label,
                "start_year": sy,
                "start_bim": sb,
                "source": "agenda2026",
            }
        )
        added += 1
    return {
        "ok": True,
        "added": added,
        "total": len(_db.list_turmas()),
        "current_bimestre": _db.get_config(),
        "missing_grades": [d for d in derived if d["missing_grade"]],
    }


@app.get("/api/canonicals")
def api_canonicals() -> dict:
    grades, db = _load()
    state = _load_state()
    cur = state["current_bimestre"]
    turmas_by_grade: dict = {}
    for t in state["turmas"]:
        turmas_by_grade.setdefault(t["grade_id"], []).append(t)

    canonicals: dict[str, list[dict]] = {}
    for g in grades:
        for m in g.modules:
            for d in g.modules[m]:
                c = _canonical_for(d, db)
                canonicals.setdefault(c, []).append(_serialize_discipline(d, db))
    items = []
    for name, offerings in sorted(canonicals.items()):
        offerings_sorted = sorted(
            offerings, key=lambda o: (o["grade_id"], _module_key(o["modulo"]))
        )
        for o in offerings_sorted:
            _attach_turmas(o, turmas_by_grade, cur)
        ementa = next(
            (o["ementa"] for o in offerings_sorted if o.get("ementa")), None
        )
        items.append(
            {
                "canonical": name,
                "offerings": offerings_sorted,
                "grade_count": len({o["grade_id"] for o in offerings_sorted}),
                "ementa_sample": ementa,
                "search_key": _fold(name),
            }
        )
    return {"canonicals": items, "current_bimestre": cur}


@app.post("/api/reload")
def api_reload() -> dict:
    _cache.clear()
    _load()
    return {"ok": True}


@app.get("/api/health")
def api_health() -> dict:
    grades, db = _load()
    state = _load_state()
    return {
        "grades": len(grades),
        "disciplines": sum(len(m) for g in grades for m in g.modules.values()),
        "canonicals": len(db.canonical_names),
        "turmas": len(state.get("turmas", [])),
        "current_bimestre": state["current_bimestre"],
    }


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def root() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8765)

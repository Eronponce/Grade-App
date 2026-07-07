"""SQLite persistence for Grade Lab.

Schema:
  config (single row): current bimestre
  turmas: list of turmas with start bim

Editable directly with any SQLite tool (DB Browser, DBeaver, sqlite3 CLI).
"""
from __future__ import annotations
import json
import sqlite3
import uuid
from pathlib import Path

from config import DB_PATH, STATE_PATH


DEFAULT_BIM = {"year": 2026, "bim": 2}


def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    return con


def init_db() -> None:
    """Create tables if missing. Seed from state.json if DB is empty."""
    with _conn() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS config (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                current_year INTEGER NOT NULL,
                current_bim INTEGER NOT NULL CHECK (current_bim BETWEEN 1 AND 4),
                updated_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS turmas (
                id TEXT PRIMARY KEY,
                grade_id TEXT NOT NULL,
                label TEXT NOT NULL,
                start_year INTEGER NOT NULL,
                start_bim INTEGER NOT NULL CHECK (start_bim BETWEEN 1 AND 4),
                source TEXT DEFAULT 'manual',
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_turmas_grade ON turmas(grade_id);
            """
        )
        con.execute(
            "INSERT OR IGNORE INTO config (id, current_year, current_bim) VALUES (1, ?, ?)",
            (DEFAULT_BIM["year"], DEFAULT_BIM["bim"]),
        )

    # Seed from legacy state.json if DB empty
    if _count_turmas() == 0 and STATE_PATH.exists():
        _seed_from_state_json(STATE_PATH)


def _count_turmas() -> int:
    with _conn() as con:
        return con.execute("SELECT COUNT(*) c FROM turmas").fetchone()["c"]


def _seed_from_state_json(state_path: Path) -> int:
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return 0
    cur = data.get("current_bimestre", DEFAULT_BIM)
    set_config(cur.get("year", DEFAULT_BIM["year"]), cur.get("bim", DEFAULT_BIM["bim"]))
    turmas = data.get("turmas", [])
    n = 0
    for t in turmas:
        # tolerate old schema fields
        sy = t.get("start_year")
        sb = t.get("start_bim")
        if sy is None or sb is None:
            continue
        try:
            create_turma(
                {
                    "id": t.get("id") or str(uuid.uuid4())[:8],
                    "grade_id": t["grade_id"],
                    "label": t.get("label", "Turma"),
                    "start_year": int(sy),
                    "start_bim": int(sb),
                    "source": t.get("source", "manual"),
                }
            )
            n += 1
        except sqlite3.IntegrityError:
            continue
    return n


def get_config() -> dict:
    with _conn() as con:
        row = con.execute(
            "SELECT current_year, current_bim FROM config WHERE id=1"
        ).fetchone()
        if not row:
            return DEFAULT_BIM.copy()
        return {"year": row["current_year"], "bim": row["current_bim"]}


def set_config(year: int, bim: int) -> None:
    with _conn() as con:
        con.execute(
            "UPDATE config SET current_year=?, current_bim=?, updated_at=datetime('now') WHERE id=1",
            (int(year), int(bim)),
        )


def list_turmas() -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT id, grade_id, label, start_year, start_bim, source FROM turmas ORDER BY grade_id, label"
        ).fetchall()
        return [dict(r) for r in rows]


def get_turma(turma_id: str) -> dict | None:
    with _conn() as con:
        row = con.execute(
            "SELECT id, grade_id, label, start_year, start_bim, source FROM turmas WHERE id=?",
            (turma_id,),
        ).fetchone()
        return dict(row) if row else None


def create_turma(t: dict) -> dict:
    with _conn() as con:
        con.execute(
            "INSERT INTO turmas (id, grade_id, label, start_year, start_bim, source) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                t["id"],
                t["grade_id"],
                t["label"],
                int(t["start_year"]),
                int(t["start_bim"]),
                t.get("source", "manual"),
            ),
        )
    return t


def update_turma(turma_id: str, updates: dict) -> dict | None:
    allowed = {"label", "start_year", "start_bim", "grade_id", "source"}
    fields = {k: v for k, v in updates.items() if k in allowed}
    if not fields:
        return get_turma(turma_id)
    cols = ", ".join(f"{k}=?" for k in fields)
    values = list(fields.values()) + [turma_id]
    with _conn() as con:
        cur = con.execute(f"UPDATE turmas SET {cols} WHERE id=?", values)
        if cur.rowcount == 0:
            return None
    return get_turma(turma_id)


def delete_turma(turma_id: str) -> bool:
    with _conn() as con:
        cur = con.execute("DELETE FROM turmas WHERE id=?", (turma_id,))
        return cur.rowcount > 0


def clear_turmas(only_source: str | None = None) -> int:
    with _conn() as con:
        if only_source:
            cur = con.execute("DELETE FROM turmas WHERE source=?", (only_source,))
        else:
            cur = con.execute("DELETE FROM turmas")
        return cur.rowcount


if __name__ == "__main__":
    init_db()
    print("DB initialized at:", DB_PATH)
    print("config:", get_config())
    print("turmas:", len(list_turmas()))

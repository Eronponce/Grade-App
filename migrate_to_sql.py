#!/usr/bin/env python3
"""Migrate grades + ementas from XLSX to SQLite."""
import sqlite3
from pathlib import Path
import openpyxl

from loader import load_grades
from canonical import load_canonical, enrich_ementas_from_ads2000
from config import DB_PATH, GRADES_DIR, EMENTAS_PATH, ADS2000_PATH


def init_schema():
    """Create grades schema."""
    with sqlite3.connect(str(DB_PATH)) as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS disciplines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT NOT NULL UNIQUE,
                nome TEXT,
                ch_teo REAL DEFAULT 0,
                ch_pra REAL DEFAULT 0,
                ch_ext REAL DEFAULT 0,
                ch_total REAL DEFAULT 0,
                modulo TEXT,
                grade_id TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS grades (
                id TEXT PRIMARY KEY,
                nome_completo TEXT NOT NULL UNIQUE,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS ementas (
                codigo TEXT PRIMARY KEY,
                ementa TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_disc_grade ON disciplines(grade_id);
            CREATE INDEX IF NOT EXISTS idx_disc_modulo ON disciplines(modulo);
        """)


def load_ementas_from_xlsx(path: Path) -> dict[str, str]:
    """Parse ementas XLSX, return {codigo: ementa}."""
    ementas = {}
    try:
        wb = openpyxl.load_workbook(str(path))
        ws = wb.active
        for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
            codigo = row[0].value
            ementa = row[1].value
            if codigo:
                ementas[str(codigo).strip()] = str(ementa or "").strip()
    except Exception as e:
        print(f"Warning: Could not load ementas from {path}: {e}")
    return ementas


def migrate():
    """Load from XLSX via loader.py, save to SQL."""
    init_schema()

    # Use existing loader
    print("Loading grades from XLSX...")
    grades = load_grades(str(GRADES_DIR))

    print("Loading canonical DB...")
    db = load_canonical(str(EMENTAS_PATH))
    if ADS2000_PATH.exists():
        print("Enriching with ADS2000 supplements...")
        enrich_ementas_from_ads2000(db, str(ADS2000_PATH))

    with sqlite3.connect(str(DB_PATH)) as con:
        # Insert grades
        for grade in grades:
            con.execute(
                "INSERT OR IGNORE INTO grades (id, nome_completo) VALUES (?, ?)",
                (grade.id, grade.nome_completo)
            )

        # Insert disciplines
        for grade in grades:
            for modulo, disciplines in grade.modules.items():
                for disc in disciplines:
                    con.execute(
                        """INSERT OR REPLACE INTO disciplines
                           (codigo, nome, ch_teo, ch_pra, ch_ext, ch_total, modulo, grade_id)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (disc.codigo, disc.nome, disc.ch_teo, disc.ch_pra,
                         disc.ch_ext, disc.ch_total, str(modulo), disc.grade_id)
                    )

        # Insert ementas from canonical DB
        for codigo in db.canonical_names:
            ementa = db.ementa_for(codigo)
            if ementa:
                con.execute(
                    "INSERT OR REPLACE INTO ementas (codigo, ementa) VALUES (?, ?)",
                    (codigo, ementa)
                )

        con.commit()

    # Stats
    with sqlite3.connect(str(DB_PATH)) as con:
        grades_count = con.execute("SELECT COUNT(*) FROM grades").fetchone()[0]
        discs_count = con.execute("SELECT COUNT(*) FROM disciplines").fetchone()[0]
        ementas_count = con.execute("SELECT COUNT(*) FROM ementas").fetchone()[0]

    print(f"\nOK Migration done:")
    print(f"   Grades: {grades_count}")
    print(f"   Disciplines: {discs_count}")
    print(f"   Ementas: {ementas_count}")


if __name__ == "__main__":
    migrate()

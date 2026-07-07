"""Load grades from SQLite instead of XLSX."""
from __future__ import annotations
import sqlite3
from dataclasses import dataclass, field

from config import DB_PATH


@dataclass
class Discipline:
    codigo: str
    nome: str
    ch_teo: float
    ch_pra: float
    ch_ext: float
    ch_total: float
    modulo: int | str
    grade_id: str


@dataclass
class Grade:
    id: str
    nome_completo: str
    modules: dict[int | str, list[Discipline]] = field(default_factory=dict)


class CanonicalDB:
    """In-memory ementas store."""
    def __init__(self):
        self.canonical_names = set()
        self._ementas = {}

    def canonical_for(self, codigo: str, nome: str = "") -> str:
        return codigo

    def ementa_for(self, codigo: str) -> str | None:
        return self._ementas.get(codigo)

    def add_ementa(self, codigo: str, ementa: str):
        self._ementas[codigo] = ementa
        self.canonical_names.add(codigo)


def load_grades_sql() -> list[Grade]:
    """Load grades from SQLite."""
    grades_dict: dict[str, Grade] = {}

    with sqlite3.connect(str(DB_PATH)) as con:
        con.row_factory = sqlite3.Row

        # Load grades
        for row in con.execute("SELECT id, nome_completo FROM grades"):
            grade = Grade(id=row["id"], nome_completo=row["nome_completo"])
            grades_dict[grade.id] = grade

        # Load disciplines grouped by grade + modulo
        for row in con.execute("""
            SELECT codigo, nome, ch_teo, ch_pra, ch_ext, ch_total, modulo, grade_id
            FROM disciplines ORDER BY grade_id, modulo
        """):
            grade = grades_dict.get(row["grade_id"])
            if not grade:
                continue

            # Parse modulo (can be int or string like "Introdutório")
            modulo = row["modulo"]
            try:
                modulo = int(modulo)
            except (ValueError, TypeError):
                pass

            disc = Discipline(
                codigo=row["codigo"],
                nome=row["nome"] or "",
                ch_teo=row["ch_teo"] or 0.0,
                ch_pra=row["ch_pra"] or 0.0,
                ch_ext=row["ch_ext"] or 0.0,
                ch_total=row["ch_total"] or 0.0,
                modulo=modulo,
                grade_id=row["grade_id"],
            )

            if modulo not in grade.modules:
                grade.modules[modulo] = []
            grade.modules[modulo].append(disc)

    return list(grades_dict.values())


def load_canonical_sql() -> CanonicalDB:
    """Load ementas from SQLite."""
    db = CanonicalDB()

    with sqlite3.connect(str(DB_PATH)) as con:
        con.row_factory = sqlite3.Row
        for row in con.execute("SELECT codigo, ementa FROM ementas WHERE ementa IS NOT NULL"):
            db.add_ementa(row["codigo"], row["ementa"])

    return db

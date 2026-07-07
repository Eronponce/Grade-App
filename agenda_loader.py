"""Parse Agenda de Encontros Sincronos xlsx to derive turmas + current module per grade."""
from __future__ import annotations
import re
from dataclasses import dataclass
from pathlib import Path

import openpyxl

from loader import CODE_RE, load_grades


# Course sheet name → prefix used for grade IDs
COURSE_MAP = {
    "ADS": "ADS",
    "EGS": "EGS",
    "CD&IA": "CIA",
    "IAR": "IAR",
    "SCI": "SCI",
}

# Núcleo comum códigos (turma 2026) → nome canônico + módulo grade
# Turma 2026 M1 2026 = mod 1 grade (Empreendedorismo, Ger. Projetos)
# Turma 2026 M2 2026 = mod 2 grade (Direito, Arquitetura)
NUCLEO_COMUM_MOD = {
    ("EMPGN@002", "II"): 1,
    ("GPR@001", "II"): 1,
    ("NODE@002", "II"): 2,
    ("AOC@010", "II"): 2,
    ("EMP@100", "II"): 1,
    ("GPR@100", "II"): 1,
    ("LPC@100", "II"): 2,
    ("AOC@100", "II"): 2,
    ("EMPGN@002", "I"): 1,
    ("GPR@001", "I"): 1,
    ("EMP@100", "I"): 1,
    ("GPR@100", "I"): 1,
}

# For turma 2026, which grade to attach (course → grade_id)
GRADE_FOR_2026 = {
    "ADS": "ADS 6000",
    "EGS": "EGS 3000",
    "CIA": "CIA 3000",
    "IAR": "IAR 1000",
    "SCI": "SCI 1000",
}


@dataclass
class AgendaEntry:
    course: str
    turma_year: int
    agenda_module: str  # 'I' / 'II'
    codigo: str
    disciplina: str
    professor: str | None


def parse_agenda(path: str | Path) -> list[AgendaEntry]:
    wb = openpyxl.load_workbook(str(path), data_only=True)
    out: list[AgendaEntry] = []
    for sheet_name, course in COURSE_MAP.items():
        if sheet_name not in wb.sheetnames:
            continue
        ws = wb[sheet_name]
        current_mod = None
        for row in ws.iter_rows(values_only=True):
            a = row[0]
            if isinstance(a, str):
                m = re.search(r"M[OÓ]DULO\s+(\w+)", a, re.IGNORECASE)
                if m:
                    current_mod = m.group(1).upper()
                    continue
            codigo = row[1] if len(row) > 1 else None
            turma = row[3] if len(row) > 3 else None
            disc = row[0]
            prof = row[4] if len(row) > 4 else None
            if not isinstance(codigo, str) or "@" not in codigo:
                continue
            if not isinstance(turma, (int, float)):
                continue
            out.append(
                AgendaEntry(
                    course=course,
                    turma_year=int(turma),
                    agenda_module=current_mod or "?",
                    codigo=codigo.strip(),
                    disciplina=str(disc or "").strip(),
                    professor=str(prof) if prof else None,
                )
            )
    wb.close()
    return out


def _code_index(grades) -> dict[str, tuple[str, int | str]]:
    idx = {}
    for g in grades:
        for mod, ds in g.modules.items():
            for d in ds:
                idx[d.codigo] = (g.id, mod)
    return idx


def derive_turmas(
    entries: list[AgendaEntry], grades_dir: str
) -> list[dict]:
    """Derive one turma per (course, turma_year) with grade_id + best-guess current module.

    Uses M2 (later bimestre) entries preferentially, since those are 'most recent completed'.
    Falls back to M1 when no M2 data.
    """
    grades = load_grades(grades_dir)
    code_idx = _code_index(grades)

    from collections import defaultdict

    grouped: dict[tuple[str, int], list[AgendaEntry]] = defaultdict(list)
    for e in entries:
        grouped[(e.course, e.turma_year)].append(e)

    turmas: list[dict] = []
    for (course, year), group in sorted(grouped.items()):
        # prefer M2 entries
        m2 = [e for e in group if e.agenda_module == "II"]
        pool = m2 if m2 else [e for e in group if e.agenda_module == "I"]
        grade_id: str | None = None
        module: int | str | None = None
        for e in pool:
            if e.codigo in code_idx:
                grade_id, module = code_idx[e.codigo]
                break
        if grade_id is None:
            # Núcleo comum (typically turma 2026): map by heuristic
            if year >= 2026 and course in GRADE_FOR_2026:
                grade_id = GRADE_FOR_2026[course]
                mods = [
                    NUCLEO_COMUM_MOD.get((e.codigo, e.agenda_module))
                    for e in pool
                ]
                mods = [m for m in mods if m is not None]
                module = max(mods) if mods else 1
            else:
                continue
        # skip if grade not loaded (e.g., CIA 3000 missing)
        if grade_id not in {g.id for g in grades}:
            turmas.append(
                {
                    "grade_id": grade_id,
                    "turma_year": year,
                    "course": course,
                    "current_module": str(module) if module else "1",
                    "missing_grade": True,
                }
            )
            continue
        turmas.append(
            {
                "grade_id": grade_id,
                "turma_year": year,
                "course": course,
                "current_module": str(module) if module else "1",
                "missing_grade": False,
            }
        )
    return turmas


if __name__ == "__main__":
    from config import AGENDA_PATH, GRADES_DIR

    if not AGENDA_PATH.exists():
        raise SystemExit(f"agenda not found: {AGENDA_PATH}")
    entries = parse_agenda(AGENDA_PATH)
    print(f"parsed {len(entries)} agenda entries")
    turmas = derive_turmas(entries, str(GRADES_DIR))
    print(f"\nderived {len(turmas)} turmas:")
    for t in turmas:
        flag = " [MISSING GRADE]" if t["missing_grade"] else ""
        print(
            f"  {t['grade_id']} · T.{t['turma_year']} · mod {t['current_module']}{flag}"
        )

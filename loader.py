"""Parser xlsx grades → Discipline/Grade dataclasses."""
from __future__ import annotations
import glob
import os
import re
import unicodedata
from dataclasses import dataclass, field

import openpyxl


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


SIGLA_RE = re.compile(r"(ADS|EGS|CIA|SCI|IAR)\s*(\d{4})")
CODE_RE = re.compile(r"^(ADS|EGS|CIA|SCI|IAR|SINT)@\d+", re.IGNORECASE)


def _norm(s) -> str:
    if s is None:
        return ""
    return (
        unicodedata.normalize("NFKD", str(s))
        .encode("ascii", "ignore")
        .decode()
        .lower()
        .strip()
    )


def _num(x) -> float:
    if x is None:
        return 0.0
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def _find_modulo_in_row(row) -> int | str | None:
    """Return module id if row is a module header ('Módulo N' anywhere)."""
    for idx, cell in enumerate(row):
        if not cell or not isinstance(cell, str):
            continue
        n = _norm(cell)
        if n.startswith("modulo introdut") or n == "modulo introdutorio":
            return "Introdutório"
        if n == "modulo" or n == "módulo":
            # number in next non-empty col
            for j in range(idx + 1, len(row)):
                v = row[j]
                if isinstance(v, (int, float)):
                    return int(v)
                if isinstance(v, str):
                    m = re.match(r"\s*(\d+)", v)
                    if m:
                        return int(m.group(1))
            continue
        m = re.match(r"m[oó]dulo\s+(\d+)", n)
        if m:
            return int(m.group(1))
    return None


def _is_header_row(row) -> bool:
    a = row[0]
    if not a or not isinstance(a, str):
        return False
    return _norm(a) == "codigo"


def _find_code_col(row) -> int | None:
    for i, cell in enumerate(row):
        if isinstance(cell, str) and CODE_RE.match(cell.strip()):
            return i
        if isinstance(cell, str) and _norm(cell) in ("codigo comp", "codigo"):
            return i
    return None


def _extract_ch(row, code_col: int) -> tuple[float, float, float, float]:
    """Extract (teo, pra, ext, total) from row given code column position.

    Heuristics for layouts:
    - Standard (code_col=0): teo=col2, pra=col3, ext=col4, total=col5
    - ADS 3000 layout (code_col=0, but header has Modalidade/P/C/H): teo=0, pra=col3, total=col4
    - ADS 2000 flat (code_col=0, cols: teo=6, pra=7, total=8): handled by dedicated parser
    Fallback: sum numeric cells after code_col+2 (name).
    """
    vals = [_num(row[i]) if i < len(row) else 0.0 for i in range(code_col + 2, min(len(row), code_col + 8))]
    # Standard layout: 4 numeric slots after name
    if len(vals) >= 4 and any(vals):
        teo, pra, ext, total = vals[0], vals[1], vals[2], vals[3]
        if total == 0 and (teo or pra or ext):
            total = teo + pra + ext
        return teo, pra, ext, total
    if len(vals) >= 2:
        # ADS 3000-ish: only pra+total or teo+total
        return 0.0, vals[0], 0.0, vals[1] if vals[1] else vals[0]
    return 0.0, 0.0, 0.0, 0.0


STOP_KEYWORDS = ("integraliza", "matriz aprovada", "comiss")


def _parse_standard_sheet(ws, grade_id: str, nome_completo: str) -> Grade:
    grade = Grade(id=grade_id, nome_completo=nome_completo)
    current_mod: int | str | None = None
    for row in ws.iter_rows(values_only=True):
        a = row[0]
        if isinstance(a, str) and any(k in _norm(a) for k in STOP_KEYWORDS):
            current_mod = None
            continue
        mod = _find_modulo_in_row(row)
        if mod is not None:
            current_mod = mod
            grade.modules.setdefault(current_mod, [])
            continue
        if _is_header_row(row):
            continue
        if current_mod is None:
            continue
        # find code cell
        code_col = None
        for i, cell in enumerate(row):
            if isinstance(cell, str) and CODE_RE.match(cell.strip()):
                code_col = i
                break
        if code_col is None:
            continue
        codigo = row[code_col].strip()
        nome = row[code_col + 1] if code_col + 1 < len(row) else None
        teo, pra, ext, total = _extract_ch(row, code_col)
        grade.modules[current_mod].append(
            Discipline(
                codigo=codigo,
                nome=str(nome) if nome else "",
                ch_teo=teo,
                ch_pra=pra,
                ch_ext=ext,
                ch_total=total,
                modulo=current_mod,
                grade_id=grade_id,
            )
        )
    return grade


def _parse_ads2000(path: str) -> Grade:
    """ADS 2000: aba 'Disciplinas' flat (col A=código, C=nome, D=módulo, G=Teo, H=Pra, I=CH)."""
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["Disciplinas"]
    grade = Grade(id="ADS 2000", nome_completo="ADS 2000 - Análise e Desenvolvimento de Sistemas")
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue
        codigo = row[0]
        if not codigo or not isinstance(codigo, str) or not codigo.startswith("ADS@"):
            continue
        nome = row[2]
        mod_raw = row[3]
        try:
            modulo: int | str = int(mod_raw)
        except (TypeError, ValueError):
            continue
        teo = _num(row[6])
        pra = _num(row[7])
        total = _num(row[8]) or (teo + pra)
        grade.modules.setdefault(modulo, []).append(
            Discipline(
                codigo=codigo.strip(),
                nome=str(nome) if nome else "",
                ch_teo=teo,
                ch_pra=pra,
                ch_ext=0.0,
                ch_total=total,
                modulo=modulo,
                grade_id="ADS 2000",
            )
        )
    wb.close()
    return grade


def _sigla_from_filename(path: str) -> str | None:
    m = SIGLA_RE.search(os.path.basename(path))
    return f"{m.group(1)} {m.group(2)}" if m else None


def _title_from_sheet(ws) -> str:
    v = ws.cell(row=1, column=1).value
    return str(v) if v else ""


def _find_sheet(wb, target_name: str):
    tn = _norm(target_name)
    for s in wb.sheetnames:
        if _norm(s) == tn:
            return wb[s]
    return None


def load_grades(grades_dir: str) -> list[Grade]:
    grades: list[Grade] = []
    for path in sorted(glob.glob(os.path.join(grades_dir, "*.xlsx"))):
        fname = os.path.basename(path)
        if fname == "Grade ADS 2000.xlsx":
            grades.append(_parse_ads2000(path))
            continue
        wb = openpyxl.load_workbook(path, data_only=True)
        if "Curso 493" in fname or "Intelig" in fname:
            # Prévia Ricardo + Cópia = versões oficiais (batem com Ementas_v2 Equivalencias)
            for sheet_name, gid, default_title in (
                ("Prévia Ricardo Tecnologia em I.", "IAR 1000", "Inteligência Artificial - Curso 493"),
                ("Cópia de Segurança Cibernética", "SCI 1000", "CST Segurança Cibernética - Curso 491"),
            ):
                ws = _find_sheet(wb, sheet_name)
                if ws is None:
                    continue
                title = _title_from_sheet(ws) or default_title
                grades.append(_parse_standard_sheet(ws, gid, title))
            wb.close()
            continue
        ws = wb.worksheets[0]
        sigla = _sigla_from_filename(path)
        if not sigla:
            wb.close()
            continue
        title = _title_from_sheet(ws) or sigla
        grades.append(_parse_standard_sheet(ws, sigla, title))
        wb.close()
    return grades


if __name__ == "__main__":
    import sys
    grades = load_grades(sys.argv[1] if len(sys.argv) > 1 else "../grades")
    for g in grades:
        total = sum(len(d) for d in g.modules.values())
        print(f"{g.id}: {len(g.modules)} módulos, {total} disciplinas | {g.nome_completo}")

"""Calendário acadêmico EAD UniFil (extraído dos PDFs oficiais).

Estrutura: {(year, bim): {start, end, limite_inclusao_exclusao, ...}}
Datas ISO YYYY-MM-DD.
"""
from __future__ import annotations

CALENDAR: dict[tuple[int, int], dict[str, str]] = {
    # 2026 — Calendário oficial EAD Cursos de Graduação Online
    (2026, 1): {
        "start": "2026-02-23",
        "end": "2026-05-10",
        "limite_inclusao": "2026-03-06",
        "rematricula": "2026-01-07",
        "provas": "2026-04-07 a 2026-04-11",
    },
    (2026, 2): {
        "start": "2026-05-11",
        "end": "2026-07-26",
        "limite_inclusao": "2026-05-22",
        "rematricula": "2026-06-22 a 2026-07-07",
        "provas": "2026-06-23 a 2026-06-27",
    },
    (2026, 3): {
        "start": "2026-07-27",
        "end": "2026-10-04",
        "limite_inclusao": "2026-08-07",
        "rematricula": "2026-09-21 a 2026-10-07",
        "provas": "2026-09-08 a 2026-09-12",
    },
    (2026, 4): {
        "start": "2026-10-05",
        "end": "2026-12-15",
        "limite_inclusao": "2026-10-16",
        "rematricula": "2026-12-14 a 2027-01-07",
        "provas": "2026-11-13 a 2026-11-18",
    },
    # 2027 — apenas início conhecido (15/02); estimativa dos demais bimestres:
    # padrão anual EAD ~10-11 semanas/bimestre, com feriados intercalados.
    (2027, 1): {
        "start": "2027-02-15",
        "end": None,  # estimado; atualizar quando sair PDF 2027
        "limite_inclusao": None,
    },
}


def bim_info(year: int, bim: int) -> dict | None:
    return CALENDAR.get((year, bim))


def all_periods() -> list[dict]:
    out = []
    for (y, b), info in sorted(CALENDAR.items()):
        out.append({"year": y, "bim": b, **info})
    return out


if __name__ == "__main__":
    for p in all_periods():
        print(p)

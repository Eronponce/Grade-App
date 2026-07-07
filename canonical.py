"""Load Ementas_v2.xlsx: canonical names + ementas."""
from __future__ import annotations
from dataclasses import dataclass, field

import openpyxl


@dataclass
class CanonicalDB:
    code_to_canonical: dict[str, str] = field(default_factory=dict)
    code_to_ementa: dict[str, str] = field(default_factory=dict)
    canonical_names: list[str] = field(default_factory=list)

    def canonical_for(self, code: str, fallback_name: str = "") -> str:
        c = self.code_to_canonical.get(code)
        if c:
            return c
        return fallback_name or code

    def ementa_for(self, code: str) -> str | None:
        return self.code_to_ementa.get(code)


def load_canonical(ementas_path: str) -> CanonicalDB:
    db = CanonicalDB()
    wb = openpyxl.load_workbook(ementas_path, data_only=True)

    # Equivalencias: row 0 = grade names; row 1 = header (Código/Nome/CH per grade)
    ws = wb["Equivalencias"]
    rows = list(ws.iter_rows(values_only=True))
    canonicals: list[str] = []
    for r in rows[2:]:
        canonical = r[0]
        if not canonical:
            continue
        canonical = str(canonical).strip()
        canonicals.append(canonical)
        # Grade columns: indexes 1,4,7,... code at idx, name at idx+1
        for idx in range(1, len(r), 3):
            code = r[idx]
            if code and isinstance(code, str):
                db.code_to_canonical[code.strip()] = canonical
    db.canonical_names = sorted(set(canonicals))

    # Ementas_v2 Disciplinas layout has no ementa column
    wb.close()
    return db


def enrich_ementas_from_ads2000(db: CanonicalDB, ads2000_path: str) -> None:
    """Grade ADS 2000 aba Disciplinas has ementa col (idx 9) for ADS@ + SINT@ codes."""
    wb = openpyxl.load_workbook(ads2000_path, data_only=True)
    ws = wb["Disciplinas"]
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue
        code_ads = row[0]
        code_sint = row[1] if len(row) > 1 else None
        ementa = row[9] if len(row) > 9 else None
        if not ementa:
            continue
        em = str(ementa).strip()
        for c in (code_ads, code_sint):
            if c and isinstance(c, str):
                db.code_to_ementa[c.strip()] = em
    wb.close()


if __name__ == "__main__":
    import sys
    db = load_canonical(sys.argv[1] if len(sys.argv) > 1 else "../Ementas_v2.xlsx")
    enrich_ementas_from_ads2000(db, "../grades/Grade ADS 2000.xlsx")
    print(f"canonical names: {len(db.canonical_names)}")
    print(f"code-to-canonical: {len(db.code_to_canonical)}")
    print(f"code-to-ementa: {len(db.code_to_ementa)}")
    print("EGS@1039 canonical:", db.canonical_for("EGS@1039"))
    print("EGS@1039 ementa:", db.ementa_for("EGS@1039") or "N/A")
    print("ADS@2018 ementa[:80]:", (db.ementa_for("ADS@2018") or "N/A")[:80])

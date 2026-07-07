"""Reports data quality issues found in Ementas_v2.xlsx (source, not modified).

Compares canonical name (from Equivalencias) vs discipline name (from grade xlsx).
Emits list of mismatches — likely wrong entries in Equivalencias tab.
"""
from __future__ import annotations
import json
import re
import sys
import unicodedata
import urllib.request


BASE = "http://127.0.0.1:8765"


def fold(s: str) -> str:
    s = s or ""
    return (
        unicodedata.normalize("NFKD", s)
        .encode("ascii", "ignore")
        .decode()
        .lower()
    )


def tokens(s: str) -> set[str]:
    s = fold(s)
    stop = {"de", "da", "do", "das", "dos", "e", "em", "a", "o", "as", "os", "para", "por", "com"}
    return {t for t in re.findall(r"[a-z0-9]+", s) if t not in stop and len(t) > 2}


def main():
    with urllib.request.urlopen(f"{BASE}/api/canonicals") as r:
        data = json.load(r)

    problems = []
    for item in data["canonicals"]:
        canon = item["canonical"]
        canon_toks = tokens(canon)
        if not canon_toks:
            continue
        for o in item["offerings"]:
            nome = o.get("nome") or ""
            if not nome:
                continue
            nome_toks = tokens(nome)
            if not nome_toks:
                continue
            overlap = canon_toks & nome_toks
            # If ZERO overlap (or extension mismatch), flag
            if not overlap:
                problems.append(
                    {
                        "codigo": o["codigo"],
                        "grade": o["grade_id"],
                        "modulo": o["modulo"],
                        "grade_name": nome,
                        "equivalence_canonical": canon,
                    }
                )

    print(f"=== {len(problems)} códigos com mismatch entre grade e Equivalencias ===\n")
    from collections import defaultdict
    by_prefix = defaultdict(list)
    for p in problems:
        prefix = p["codigo"].split("@")[0]
        by_prefix[prefix].append(p)

    for prefix in sorted(by_prefix.keys()):
        items = by_prefix[prefix]
        print(f"\n--- {prefix} ({len(items)} problemas) ---")
        for p in items:
            print(
                f"  {p['codigo']:12s} | grade {p['grade']:10s} M{p['modulo']:>4} | "
                f"'{p['grade_name'][:35]:35s}' ->> tabela diz '{p['equivalence_canonical'][:35]}'"
            )

    print(f"\nTotal: {len(problems)} mismatches. Sugestão: revisar Equivalencias no Ementas_v2.xlsx")


if __name__ == "__main__":
    main()

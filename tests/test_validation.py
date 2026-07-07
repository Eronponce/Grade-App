"""Validation suite: fictional students vs source spreadsheet vs app API.

Verifies delta calculation, cross-grade equivalences, edge cases (DP, exclusive
disciplines, núcleo comum, etc.) by comparing:
  - Ground truth: directly parsed from xlsx grades
  - App API: HTTP responses from /api/canonicals

Prints pass/fail per scenario.
"""
from __future__ import annotations
import json
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from canonical import CanonicalDB, enrich_ementas_from_ads2000, load_canonical
from loader import Discipline, Grade, load_grades


BASE = "http://127.0.0.1:8765"
GRADES_DIR = r"G:\Meu Drive\random\grades"
EMENTAS = r"G:\Meu Drive\random\Ementas_v2.xlsx"
ADS2000 = r"G:\Meu Drive\random\grades\Grade ADS 2000.xlsx"


def http_get(path: str) -> dict:
    with urllib.request.urlopen(f"{BASE}{path}") as r:
        return json.loads(r.read().decode("utf-8"))


def module_key(m):
    return (1, m) if isinstance(m, int) else (0, str(m))


class TruthDB:
    def __init__(self):
        self.grades = {g.id: g for g in load_grades(GRADES_DIR)}
        self.canonical = load_canonical(EMENTAS)
        enrich_ementas_from_ads2000(self.canonical, ADS2000)

    def canonical_of(self, code: str, fallback: str = "") -> str:
        return self.canonical.canonical_for(code, fallback)

    def offerings_of(self, canonical_name: str) -> list[tuple[str, int | str, str, str]]:
        """(grade_id, modulo, codigo, disc_name)."""
        out = []
        for gid, g in self.grades.items():
            for mod, ds in g.modules.items():
                for d in ds:
                    if self.canonical_of(d.codigo, d.nome) == canonical_name:
                        out.append((gid, mod, d.codigo, d.nome))
        return out

    def find_module(self, grade_id: str, canonical_name: str) -> int | str | None:
        for mod, ds in self.grades[grade_id].modules.items():
            for d in ds:
                if self.canonical_of(d.codigo, d.nome) == canonical_name:
                    return mod
        return None


@dataclass
class Student:
    name: str
    grade_id: str
    turma_label: str
    current_module: int


@dataclass
class Question:
    student: Student
    canonical: str


@dataclass
class Scenario:
    label: str
    question: Question
    expected_module: int | str | None  # None if not offered in student's grade
    expected_delta: int | None  # None if not offered in student's grade OR non-numeric module
    expected_grade_count: int  # cross-grade offering count
    expected_exclusive: bool


class Runner:
    def __init__(self):
        self.truth = TruthDB()
        self.canonicals_api = {c["canonical"]: c for c in http_get("/api/canonicals")["canonicals"]}
        self.turmas_api = http_get("/api/turmas")["turmas"]
        self.results = []

    def offering_for_student(self, s: Student, canonical: str):
        item = self.canonicals_api.get(canonical)
        if not item:
            return None, None
        # find offering in student's grade
        for o in item["offerings"]:
            if o["grade_id"] == s.grade_id:
                # find turma_delta matching student's label
                turma_delta = None
                for td in o["turma_deltas"]:
                    if td["label"] == s.turma_label:
                        turma_delta = td["delta"]
                        break
                return o, turma_delta
        return None, None

    def check(self, sc: Scenario):
        s = sc.question.student
        c = sc.question.canonical
        offering, api_delta = self.offering_for_student(s, c)
        truth_mod = self.truth.find_module(s.grade_id, c)
        truth_delta = None
        if isinstance(truth_mod, int) and isinstance(s.current_module, int):
            truth_delta = truth_mod - s.current_module

        # Truth cross-grade
        truth_offerings = self.truth.offerings_of(c)
        truth_grade_count = len({o[0] for o in truth_offerings})

        # API cross-grade
        item = self.canonicals_api.get(c)
        api_grade_count = item["grade_count"] if item else 0
        api_exclusive = api_grade_count == 1

        checks = []
        # 1) Module in student's grade
        api_mod = offering["modulo"] if offering else None
        checks.append(("module", api_mod == truth_mod == sc.expected_module, f"api={api_mod} truth={truth_mod} exp={sc.expected_module}"))
        # 2) Delta
        checks.append(("delta", api_delta == truth_delta == sc.expected_delta, f"api={api_delta} truth={truth_delta} exp={sc.expected_delta}"))
        # 3) Grade count
        checks.append(("grade_count", truth_grade_count == api_grade_count == sc.expected_grade_count, f"api={api_grade_count} truth={truth_grade_count} exp={sc.expected_grade_count}"))
        # 4) Exclusive flag
        checks.append(("exclusive", api_exclusive == sc.expected_exclusive, f"api={api_exclusive} exp={sc.expected_exclusive}"))

        all_pass = all(ok for _, ok, _ in checks)
        self.results.append((sc.label, all_pass, checks, sc))
        return all_pass

    def report(self):
        passed = sum(1 for _, ok, _, _ in self.results if ok)
        total = len(self.results)
        print(f"\n{'=' * 72}\nRESUMO: {passed}/{total} cenários passaram")
        print("=" * 72)
        for label, ok, checks, sc in self.results:
            icon = "OK" if ok else "FAIL"
            s = sc.question.student
            print(f"\n[{icon}] {label}")
            print(f"       Aluno: {s.name} · {s.grade_id} · {s.turma_label} · mod {s.current_module}")
            print(f"       Pergunta: {sc.question.canonical}")
            for name, cok, detail in checks:
                ico = "  ok" if cok else "  X "
                print(f"        {ico} {name}: {detail}")
        return passed == total


# ============ Cenários ============

students = {
    "maicon": Student("Maicon Bortoli", "EGS 1000", "Turma 2023", 14),
    "ana": Student("Ana Silva", "ADS 6000", "Turma 2026", 2),
    "bruno": Student("Bruno Souza", "CIA 1000", "Turma 2023", 14),
    "carlos": Student("Carlos Nakagawa", "EGS 2000", "Turma 2024", 10),
    "debora": Student("Débora Ferreira", "IAR 1000", "Turma 2026", 2),
    "elton": Student("Elton Oliveira", "ADS 5000", "Turma 2025", 6),
    "fabiana": Student("Fabiana Costa", "SCI 1000", "Turma 2026", 2),
    "guilherme": Student("Guilherme Rocha", "EGS 3000", "Turma 2026", 2),
    "helena": Student("Helena Prado", "ADS 5000", "Turma 2024", 10),
    "igor": Student("Igor Melo", "CIA 2000", "Turma 2025", 6),
}


scenarios: list[Scenario] = [
    # 1. Maicon: PDS II - próximo módulo? Não, +2 bim
    Scenario(
        "Maicon (EGS 1000 T2023 M14) - PDS II - exclusiva EGS 1000 M16",
        Question(students["maicon"], "Projeto e Desenvolvimento de Sistema II"),
        expected_module=16, expected_delta=2, expected_grade_count=1, expected_exclusive=True,
    ),
    # 2. Maicon: PDS I - mesma coisa que PDS II (exclusiva EGS 1000 M16)
    Scenario(
        "Maicon - PDS I - exclusiva EGS 1000 M16",
        Question(students["maicon"], "Projeto e Desenvolvimento de Sistema I"),
        expected_module=16, expected_delta=2, expected_grade_count=1, expected_exclusive=True,
    ),
    # 3. Maicon: Métricas de Software - já passou (mod 10, delta -4)
    Scenario(
        "Maicon - Métricas de Software (EGS 1000 M10, já passou)",
        Question(students["maicon"], "Métricas de Software"),
        expected_module=10, expected_delta=-4, expected_grade_count=8, expected_exclusive=False,
    ),
    # 4. Maicon: Qualidade - mod 11, delta -3
    Scenario(
        "Maicon - Qualidade de Software (EGS 1000 M11, já passou)",
        Question(students["maicon"], "Qualidade de Software"),
        expected_module=11, expected_delta=-3, expected_grade_count=5, expected_exclusive=False,
    ),
    # 5. Maicon: Empreendedorismo - mod 1, delta -13, todas 12 grades têm
    Scenario(
        "Maicon - Empreendedorismo (mod 1, todas 12 grades)",
        Question(students["maicon"], "Empreendedorismo"),
        expected_module=1, expected_delta=-13, expected_grade_count=12, expected_exclusive=False,
    ),
    # 6. Ana ADS 6000 T2026 M2 - Empreendedorismo (mod 1, delta -1)
    Scenario(
        "Ana (ADS 6000 T2026 M2) - Empreendedorismo (mod 1 delta -1)",
        Question(students["ana"], "Empreendedorismo"),
        expected_module=1, expected_delta=-1, expected_grade_count=12, expected_exclusive=False,
    ),
    # 7. Carlos EGS 2000 T2024 M10 - Sistemas Operacionais (mod 10 delta 0 = agora!)
    Scenario(
        "Carlos (EGS 2000 T2024 M10) - Sistemas Operacionais (agora!)",
        Question(students["carlos"], "Sistemas Operacionais"),
        expected_module=10, expected_delta=0, expected_grade_count=8, expected_exclusive=False,
    ),
    # 8. Bruno CIA 1000 T2023 M14 - Deep Learning (deve ser mod 14 - agora)
    Scenario(
        "Bruno (CIA 1000 T2023 M14) - Deep Learning (agora)",
        Question(students["bruno"], "Deep Learning"),
        expected_module=14, expected_delta=0, expected_grade_count=2, expected_exclusive=False,
    ),
    # 9. Débora IAR 1000 T2026 M2 - Inteligência Artificial
    # NOTA: Ementas_v2 tem misalignment nas equivalencias IAR — IAR@1006 (Teoria dos Jogos)
    # está mapeado como canonical "Inteligência Artificial" (deveria ser IAR@1009).
    # Testando o que a fonte DIZ, não o que deveria ser.
    Scenario(
        "Débora (IAR 1000 T2026 M2) - Inteligência Artificial [DATA BUG IAR]",
        Question(students["debora"], "Inteligência Artificial"),
        expected_module=3, expected_delta=1, expected_grade_count=7, expected_exclusive=False,
    ),
    # 10. Elton ADS 5000 T2025 M6 - Sistemas Operacionais (ADS 5000 mod 8 delta +2)
    Scenario(
        "Elton (ADS 5000 T2025 M6) - Sistemas Operacionais (+2)",
        Question(students["elton"], "Sistemas Operacionais"),
        expected_module=8, expected_delta=2, expected_grade_count=8, expected_exclusive=False,
    ),
    # 11. Helena ADS 5000 T2024 M10 - Métricas (ADS 5000 mod 10 - agora!)
    Scenario(
        "Helena (ADS 5000 T2024 M10) - Métricas (agora)",
        Question(students["helena"], "Métricas de Software"),
        expected_module=10, expected_delta=0, expected_grade_count=8, expected_exclusive=False,
    ),
    # 12. Igor CIA 2000 T2025 M6 - Intro Machine Learning (também mapeado em IAR por bug)
    Scenario(
        "Igor (CIA 2000 T2025 M6) - Intro a Machine Learning (agora)",
        Question(students["igor"], "Introdução a Machine Learning"),
        expected_module=6, expected_delta=0, expected_grade_count=3, expected_exclusive=False,
    ),
    # 13. Aluno DP: Maicon perg sobre Sistemas Operacionais (EGS 1000 mod 8, delta -6)
    Scenario(
        "Maicon - Sistemas Operacionais (mod 8 delta -6, muito atrás)",
        Question(students["maicon"], "Sistemas Operacionais"),
        expected_module=8, expected_delta=-6, expected_grade_count=8, expected_exclusive=False,
    ),
    # 14. Aluno adiantado consulta futuro: Ana ADS 6000 M2 - Sistemas Operacionais (mod 8, +6)
    Scenario(
        "Ana (ADS 6000 T2026 M2) - Sistemas Operacionais (mod 8 delta +6)",
        Question(students["ana"], "Sistemas Operacionais"),
        expected_module=8, expected_delta=6, expected_grade_count=8, expected_exclusive=False,
    ),
    # 15. Extensão VIII - EGS 1000 mod 16; equivalencias tabela relaciona 10 grades genéricas
    Scenario(
        "Maicon - Extensão VIII (EGS 1000 mod 16, +2)",
        Question(students["maicon"], "Extensão VIII"),
        expected_module=16, expected_delta=2, expected_grade_count=12, expected_exclusive=False,
    ),
    # 16. Governança em TIC - EGS 1000 mod 14 - Maicon AGORA (acabou de fazer)
    Scenario(
        "Maicon - Governança em TIC (agora - mod 14 delta 0)",
        Question(students["maicon"], "Governança em Tecnologia da Informação e Comunicação"),
        expected_module=14, expected_delta=0, expected_grade_count=4, expected_exclusive=False,
    ),
    # 17. Guilherme EGS 3000 T2026 M2 - Sistemas Operacionais (EGS 3000 mod 10, +8)
    Scenario(
        "Guilherme (EGS 3000 T2026 M2) - Sistemas Operacionais (+8)",
        Question(students["guilherme"], "Sistemas Operacionais"),
        expected_module=10, expected_delta=8, expected_grade_count=8, expected_exclusive=False,
    ),
    # 18. Fabiana SCI 1000 T2026 M2 - Inteligência Artificial (SCI 1000 mod 4, +2)
    Scenario(
        "Fabiana (SCI 1000 T2026 M2) - Inteligência Artificial (+2)",
        Question(students["fabiana"], "Inteligência Artificial"),
        expected_module=4, expected_delta=2, expected_grade_count=7, expected_exclusive=False,
    ),
    # 19. Extensão I - Bruno CIA 1000 M14 (CIA 1000 Ext I está mod 9 na grade)
    Scenario(
        "Bruno - Extensão I (CIA 1000 mod 9, delta -5)",
        Question(students["bruno"], "Extensão I"),
        expected_module=9, expected_delta=-5, expected_grade_count=10, expected_exclusive=False,
    ),
    # 20. Cross-grade multi-turma: Carlos EGS 2000 T2024 M10 - Empreendedorismo (mod 1, -9)
    Scenario(
        "Carlos (EGS 2000 T2024 M10) - Empreendedorismo (-9)",
        Question(students["carlos"], "Empreendedorismo"),
        expected_module=1, expected_delta=-9, expected_grade_count=12, expected_exclusive=False,
    ),
    # 21. Introdutório module (ADS 6000): Ana pergunta Inovação (4 grades - ADS 6000 + IAR + SCI + outro)
    Scenario(
        "Ana (ADS 6000) - Inovação e Pensamento Criativo (introd)",
        Question(students["ana"], "Inovação e Pensamento Criativo"),
        expected_module="Introdutório", expected_delta=None, expected_grade_count=4, expected_exclusive=False,
    ),
    # 22. Elton (ADS 5000 M6) - Métricas (mod 10, +4)
    Scenario(
        "Elton (ADS 5000 T2025 M6) - Métricas (+4)",
        Question(students["elton"], "Métricas de Software"),
        expected_module=10, expected_delta=4, expected_grade_count=8, expected_exclusive=False,
    ),
    # 23. Aluno futuro: Guilherme EGS 3000 M2 pergunta PDS II (NÃO existe em EGS 3000)
    #     → offering_for_student retorna None → check pula module/delta
    Scenario(
        "Guilherme (EGS 3000) - PDS II [não existe nessa grade]",
        Question(students["guilherme"], "Projeto e Desenvolvimento de Sistema II"),
        expected_module=None, expected_delta=None, expected_grade_count=1, expected_exclusive=True,
    ),
]


def verify_multi_turma_deltas(r: Runner) -> list[tuple[str, bool, str]]:
    """Extra checks: offerings whose grade has multiple turmas should have multiple deltas."""
    checks = []
    # EGS 2000 tem T.2024 + T.2025. Sistemas Operacionais em EGS 2000 mod 10.
    # Delta esperado: T.2024 (mod 10 atual) => 0; T.2025 (mod 6) => +4
    item = r.canonicals_api.get("Sistemas Operacionais")
    for o in item["offerings"]:
        if o["grade_id"] == "EGS 2000":
            deltas = {td["label"]: td["delta"] for td in o["turma_deltas"]}
            ok = deltas.get("Turma 2024") == 0 and deltas.get("Turma 2025") == 4
            checks.append(("multi-turma SO EGS 2000", ok, f"deltas={deltas}"))
            break
    # ADS 5000 tem T.2024 + T.2025. Métricas ADS 5000 mod 10.
    # T.2024 (mod 10) => 0; T.2025 (mod 6) => +4
    item = r.canonicals_api.get("Métricas de Software")
    for o in item["offerings"]:
        if o["grade_id"] == "ADS 5000":
            deltas = {td["label"]: td["delta"] for td in o["turma_deltas"]}
            ok = deltas.get("Turma 2024") == 0 and deltas.get("Turma 2025") == 4
            checks.append(("multi-turma Métricas ADS 5000", ok, f"deltas={deltas}"))
            break
    # CIA 2000 tem T.2024 + T.2025. Empreendedorismo CIA 2000 mod 1.
    # T.2024 (mod 10) => -9; T.2025 (mod 6) => -5
    item = r.canonicals_api.get("Empreendedorismo")
    for o in item["offerings"]:
        if o["grade_id"] == "CIA 2000":
            deltas = {td["label"]: td["delta"] for td in o["turma_deltas"]}
            ok = deltas.get("Turma 2024") == -9 and deltas.get("Turma 2025") == -5
            checks.append(("multi-turma Empreendedorismo CIA 2000", ok, f"deltas={deltas}"))
            break
    # ADS 6000 turma 2026 apenas: 1 delta chip
    item = r.canonicals_api.get("Empreendedorismo")
    for o in item["offerings"]:
        if o["grade_id"] == "ADS 6000":
            labels = [td["label"] for td in o["turma_deltas"]]
            ok = len(labels) == 1 and labels[0] == "Turma 2026"
            checks.append(("ADS 6000 apenas T.2026", ok, f"labels={labels}"))
            break
    return checks


def main():
    r = Runner()
    print("Rodando validações...\n")
    for sc in scenarios:
        r.check(sc)
    all_ok = r.report()

    # Extra multi-turma checks
    print("\n" + "=" * 72)
    print("VERIFICAÇÕES MULTI-TURMA (mesma grade, várias turmas)")
    print("=" * 72)
    mt_checks = verify_multi_turma_deltas(r)
    all_mt_ok = True
    for name, ok, detail in mt_checks:
        ico = "OK" if ok else "FAIL"
        print(f"  [{ico}] {name}: {detail}")
        if not ok:
            all_mt_ok = False

    return 0 if (all_ok and all_mt_ok) else 1


if __name__ == "__main__":
    sys.exit(main())

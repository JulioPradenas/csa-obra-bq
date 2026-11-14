#!/usr/bin/env python3
"""
CSA Obra — Paso 5: vistas planas de csa_gold para Looker Studio.

Uso (Mac de Julio, ADC):
  export GCP_PROJECT=csa-obra-jp
  python scripts/build_looker_views.py --dry-run
  python scripts/build_looker_views.py

Crea tres vistas (CREATE OR REPLACE VIEW, sin DML) y comprueba que dan los
mismos valores sin filtro que gold. Imprime RESULTADO: OK o RESULTADO: FALLA.
"""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path

from apply_ddl import split_statements
from bq_env import GOLD_DATASET, LOCATION, ROOT, build_client, load_project_id

SQL_DIR = ROOT / "sql" / "looker"
SQL_FILES = (
    "01_v_avance_semana.sql",
    "02_v_hh_dia.sql",
    "03_v_consumo_semana.sql",
)

# (nombre, consulta, esperado, tolerancia)
CHECKS = (
    ("v_avance_semana filas", "SELECT COUNT(*) FROM `csa_gold.v_avance_semana`", Decimal("735"), Decimal("0")),
    (
        "SUM(monto_contrato) una vez por partida",
        "SELECT SUM(monto_contrato) FROM `csa_gold.v_avance_semana`",
        Decimal("6879075000"),
        Decimal("0.5"),
    ),
    (
        "SPI sin filtro",
        "SELECT SUM(monto_ejecutado) / SUM(monto_programado) FROM `csa_gold.v_avance_semana`",
        Decimal("0.8978"),
        Decimal("0.0001"),
    ),
    (
        "% avance físico sin filtro",
        "SELECT SUM(monto_ejecutado) / SUM(monto_contrato) FROM `csa_gold.v_avance_semana`",
        Decimal("0.7183"),
        Decimal("0.0001"),
    ),
    ("v_hh_dia filas", "SELECT COUNT(*) FROM `csa_gold.v_hh_dia`", Decimal("1470"), Decimal("0")),
    ("SUM(hh)", "SELECT SUM(hh) FROM `csa_gold.v_hh_dia`", Decimal("42707.70"), Decimal("0.01")),
    (
        "HH por m³ cuadrillas de tierras",
        "SELECT SUM(hh) / SUM(cantidad_ejecutada) FROM `csa_gold.v_hh_dia` WHERE especialidad = 'tierras'",
        Decimal("0.9101"),
        Decimal("0.0001"),
    ),
    ("v_consumo_semana filas", "SELECT COUNT(*) FROM `csa_gold.v_consumo_semana`", Decimal("882"), Decimal("0")),
    (
        "desviación sin filtro",
        "SELECT (SUM(monto_real) - SUM(monto_presupuestado)) / SUM(monto_presupuestado) FROM `csa_gold.v_consumo_semana`",
        Decimal("0.0455"),
        Decimal("0.0001"),
    ),
)


def sql_files() -> list[Path]:
    return [SQL_DIR / name for name in SQL_FILES]


def statements() -> list[tuple[Path, str]]:
    out: list[tuple[Path, str]] = []
    for path in sql_files():
        for stmt in split_statements(path.read_text(encoding="utf-8")):
            out.append((path, stmt))
    return out


def run(*, dry_run: bool = False, project_id: str | None = None, client=None) -> int:
    missing = [path for path in sql_files() if not path.is_file()]
    if missing:
        print("Faltan SQL de vistas:", file=sys.stderr)
        for path in missing:
            print(f"  {path}", file=sys.stderr)
        return 1
    stmts = statements()
    print(f"location={LOCATION}")
    print(f"dataset={GOLD_DATASET}")
    print(f"dry_run={dry_run}")
    print(f"statements={len(stmts)}")
    if dry_run:
        for path, stmt in stmts:
            print(f"  would_run  {path.name}  {stmt.splitlines()[0]}")
        print("dry-run: no se crearon vistas ni se consultó BigQuery.")
        return 0

    project = project_id or load_project_id()
    print(f"project={project}")
    bq = client if client is not None else build_client(project)
    for path, stmt in stmts:
        bq.query(stmt, location=LOCATION).result()
        print(f"  replaced  {path.name}  {stmt.splitlines()[0]}")

    ok = True
    print()
    print(f"{'control':42} {'esperado':>16} {'observado':>16}  resultado")
    for name, sql, expected, tol in CHECKS:
        row = list(bq.query(sql, location=LOCATION).result())[0]
        observed = Decimal(str(row[0]))
        good = abs(observed - expected) <= tol
        ok = ok and good
        print(f"{name:42} {str(expected):>16} {str(observed.quantize(Decimal('0.0001'))):>16}  {'OK' if good else 'FALLA'}")
    print()
    print("RESULTADO: OK" if ok else "RESULTADO: FALLA")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Crea las vistas de csa_gold para Looker Studio.")
    parser.add_argument("--dry-run", action="store_true", help="Muestra el SQL. No llama a BigQuery.")
    args = parser.parse_args(argv)
    return run(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())

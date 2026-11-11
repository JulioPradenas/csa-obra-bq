#!/usr/bin/env python3
"""
CSA Obra — Paso 4: silver → gold.

Uso (Mac de Julio, ADC):
  export GCP_PROJECT=csa-obra-jp
  python scripts/build_gold.py --dry-run
  python scripts/build_gold.py

Sandbox: solo CREATE OR REPLACE TABLE ... AS SELECT. Sin DML, sin streaming,
sin partición por fecha. CLUSTER BY. Cada tabla expira a los 60 días.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from apply_ddl import ensure_dataset, split_statements
from bq_env import (
    EXPIRATION_DAYS,
    GOLD_DATASET,
    LOCATION,
    NOTICE,
    ROOT,
    build_client,
    load_project_id,
)

SQL_DIR = ROOT / "sql" / "gold"
SQL_FILES = (
    "01_d_obra.sql",
    "02_d_proveedor.sql",
    "03_d_partida.sql",
    "04_d_cuadrilla.sql",
    "05_d_material.sql",
    "06_d_fecha.sql",
    "07_f_avance_partida.sql",
    "08_f_hh_cuadrilla.sql",
    "09_f_consumo_material.sql",
)


def sql_files() -> list[Path]:
    return [SQL_DIR / name for name in SQL_FILES]


def run(*, dry_run: bool = False, project_id: str | None = None, client=None) -> int:
    files = sql_files()
    missing = [path for path in files if not path.is_file()]
    if missing:
        print("Faltan SQL de gold:", file=sys.stderr)
        for path in missing:
            print(f"  {path}", file=sys.stderr)
        return 1
    print(f"location={LOCATION}")
    print(f"dataset={GOLD_DATASET}")
    print(f"expiration_days={EXPIRATION_DAYS}")
    print(f"dry_run={dry_run}")
    statements: list[tuple[Path, str]] = []
    for path in files:
        for stmt in split_statements(path.read_text(encoding="utf-8")):
            statements.append((path, stmt))
    print(f"statements={len(statements)}")
    if dry_run:
        for path, stmt in statements:
            print(f"  would_run  {path.name}  {stmt.splitlines()[0]}")
        print("dry-run: no se creó csa_gold ni se ejecutó SQL.")
        return 0

    project = project_id or load_project_id()
    print(f"project={project}")
    bq = client if client is not None else build_client(project)
    action = ensure_dataset(
        bq,
        project,
        GOLD_DATASET,
        description=(
            f"{NOTICE} Gold para el jefe de obra. Sin partición por fecha. "
            f"Tablas expiran a los {EXPIRATION_DAYS} días. make run reconstruye desde cero."
        ),
    )
    print(f"  dataset {action}  {project}.{GOLD_DATASET}")
    for path, stmt in statements:
        job = bq.query(stmt, location=LOCATION)
        job.result()
        print(f"  replaced  {path.name}  {stmt.splitlines()[0]}")
    print(f"OK: {GOLD_DATASET} reconstruido (CREATE OR REPLACE AS SELECT, CLUSTER BY).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Construye csa_gold desde csa_silver.")
    parser.add_argument("--dry-run", action="store_true", help="Muestra el SQL. No llama a BigQuery.")
    args = parser.parse_args(argv)
    return run(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())

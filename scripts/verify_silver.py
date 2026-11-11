#!/usr/bin/env python3
"""
Reconcilia bronze = silver + cuarentena, motivos contra el manifest y 0 huérfanas.

Dry-run clasifica los CSV con la misma prioridad que el SQL (sin BigQuery).
La corrida real cuenta en csa_bronze y csa_silver.
Imprime una tabla y RESULTADO: OK o RESULTADO: FALLA.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bq_env import LOCATION, ROOT, SILVER_DATASET, build_client, load_project_id
from contrato import FK_RULES, MOTIVOS, TABLE_ORDER
from csv_io import read_rows
from motivos import clasificar, contar, huerfanas_en_silver
from verify_bronze import RAW_DIR, load_manifest

BRONZE = "csa_bronze"


def _load_tables(raw_dir: Path) -> dict[str, list[dict[str, str]]]:
    tables = {}
    for table in TABLE_ORDER:
        path = raw_dir / f"{table}.csv"
        if not path.is_file():
            raise SystemExit(f"Falta el CSV {path}. Corre `make data` primero.")
        tables[table] = read_rows(path)
    return tables


def _observed_from_frames(tables: dict[str, list[dict[str, str]]]) -> dict:
    motives = clasificar(tables)
    conteos = contar(motives)
    bronze = {table: len(tables[table]) for table in TABLE_ORDER}
    silver = {}
    for table in TABLE_ORDER:
        labels = motives[table]
        silver_n = sum(1 for label in labels if label is None)
        silver[table] = {"silver": silver_n, "cuarentena": len(labels) - silver_n, "motivos": conteos[table]}
    return {
        "bronze": bronze,
        "tablas": silver,
        "huerfanas": huerfanas_en_silver(tables, motives),
    }


def _query_one(client, sql: str) -> list[dict]:
    job = client.query(sql, location=LOCATION)
    return [dict(row) for row in job.result()]


def _huerfanas_sql(project: str, table: str) -> str | None:
    rules = FK_RULES.get(table)
    if not rules:
        return None
    joins = []
    wheres = []
    seen: set[str] = set()
    for column, parent, parent_pk, misma_obra in rules:
        alias = f"p_{parent}"
        if parent not in seen:
            joins.append(
                f"LEFT JOIN `{project}.{SILVER_DATASET}.{parent}` {alias} "
                f"ON e.{column} = {alias}.{parent_pk}"
            )
            seen.add(parent)
        wheres.append(f"{alias}.{parent_pk} IS NULL")
        if misma_obra is not None:
            wheres.append(f"{alias}.{misma_obra} != e.{misma_obra}")
    where = " OR ".join(wheres)
    join_sql = " ".join(joins)
    return (
        "SELECT COUNT(*) AS n "
        f"FROM `{project}.{SILVER_DATASET}.{table}` e {join_sql} "
        f"WHERE {where}"
    )


def _observed_from_bq(client, project: str) -> dict:
    bronze = {}
    tablas = {}
    huerfanas = 0
    for table in TABLE_ORDER:
        bronze_n = int(
            _query_one(client, f"SELECT COUNT(*) AS n FROM `{project}.{BRONZE}.{table}`")[0]["n"]
        )
        silver_n = int(
            _query_one(
                client, f"SELECT COUNT(*) AS n FROM `{project}.{SILVER_DATASET}.{table}`"
            )[0]["n"]
        )
        q_n = int(
            _query_one(
                client, f"SELECT COUNT(*) AS n FROM `{project}.{SILVER_DATASET}.q_{table}`"
            )[0]["n"]
        )
        bronze[table] = bronze_n
        motivos = {motivo: 0 for motivo in MOTIVOS}
        rows = _query_one(
            client,
            "SELECT motivo, COUNT(*) AS n "
            f"FROM `{project}.{SILVER_DATASET}.q_{table}` GROUP BY motivo",
        )
        for row in rows:
            motivos[str(row["motivo"])] = int(row["n"])
        tablas[table] = {"silver": silver_n, "cuarentena": q_n, "motivos": motivos}
        sql = _huerfanas_sql(project, table)
        if sql:
            huerfanas += int(_query_one(client, sql)[0]["n"])
    return {"bronze": bronze, "tablas": tablas, "huerfanas": huerfanas}


def render_report(manifest: dict, observed: dict) -> tuple[str, bool]:
    lineas = [f"{'tabla':<22} {'bronze':>8} {'silver':>8} {'q':>8}  resultado"]
    lineas.append("-" * len(lineas[0]))
    ok = True
    for table in TABLE_ORDER:
        bronze_n = int(observed["bronze"][table])
        silver_n = int(observed["tablas"][table]["silver"])
        q_n = int(observed["tablas"][table]["cuarentena"])
        want_bronze = int(manifest["row_counts"][table])
        want_silver = int(manifest["clean_counts"][table])
        want_q = sum(int(manifest["anomalies"][table][motivo]) for motivo in MOTIVOS)
        good = (
            bronze_n == silver_n + q_n
            and bronze_n == want_bronze
            and silver_n == want_silver
            and q_n == want_q
        )
        if not good:
            ok = False
        lineas.append(
            f"{table:<22} {bronze_n:8d} {silver_n:8d} {q_n:8d}  {'OK' if good else 'FALLA'}"
        )
    lineas.append("")
    lineas.append(f"{'tabla':<22} {'motivo':<22} {'manifest':>8} {'observado':>10}  resultado")
    for table in TABLE_ORDER:
        for motivo in MOTIVOS:
            want = int(manifest["anomalies"][table][motivo])
            got = int(observed["tablas"][table]["motivos"].get(motivo, 0))
            if want == 0 and got == 0:
                continue
            good = want == got
            if not good:
                ok = False
            lineas.append(
                f"{table:<22} {motivo:<22} {want:8d} {got:10d}  {'OK' if good else 'FALLA'}"
            )
    huerfanas = int(observed["huerfanas"])
    if huerfanas != 0:
        ok = False
    lineas.append("")
    lineas.append(f"huerfanas_en_silver {huerfanas}")
    lineas.append("RESULTADO: " + ("OK" if ok else "FALLA"))
    return "\n".join(lineas), ok


def run(
    *,
    dry_run: bool = False,
    project_id: str | None = None,
    client=None,
    manifest_path: Path | None = None,
    raw_dir: Path = RAW_DIR,
) -> int:
    manifest = load_manifest(manifest_path or (ROOT / "data" / "manifest.json"))
    if dry_run:
        print(f"location={LOCATION}")
        print("dry_run=True")
        observed = _observed_from_frames(_load_tables(raw_dir))
    else:
        project = project_id or load_project_id()
        print(f"project={project}")
        print(f"location={LOCATION}")
        bq = client if client is not None else build_client(project)
        observed = _observed_from_bq(bq, project)
    report, ok = render_report(manifest, observed)
    print(report)
    if not ok:
        print("VERIFY FALLA: silver no cuadra con el manifest.", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compara bronze, silver y q_<tabla> contra el manifest."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Clasifica los CSV. No consulta BigQuery.",
    )
    args = parser.parse_args(argv)
    return run(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())

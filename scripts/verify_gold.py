#!/usr/bin/env python3
"""
Compara la estrella gold con la simulación local y con la historia del lab.

Dry-run no consulta BigQuery: clasifica los CSV y arma los hechos en memoria.
La corrida real compara conteos y sumas de csa_gold contra esa simulación.
Imprime RESULTADO: OK o RESULTADO: FALLA.
"""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path

from bq_env import GOLD_DATASET, LOCATION, ROOT, build_client, load_project_id
from csv_io import read_rows
from gold_sim import GOLD_ORDER, q2, simular
from verify_bronze import RAW_DIR

# Anclas de la historia. Si el generador cambia el ratio, esto tiene que fallar
# a la vista, no redondearse en silencio.
ANCLAS = {
    "spi_obr_01": Decimal("0.70"),
    "avance_obr_01": Decimal("0.56"),
    "spi_obr_02": Decimal("1.05"),
    "spi_obr_06": Decimal("0.55"),
    "desviacion_asfalto_coronel": Decimal("0.40"),
    "hh_tierras_obr_01": Decimal("1.40"),
    "hh_tierras_obr_02": Decimal("0.80"),
}


def _load_tables(raw_dir: Path) -> dict[str, list[dict[str, str]]]:
    from contrato import TABLE_ORDER

    tables = {}
    for table in TABLE_ORDER:
        path = raw_dir / f"{table}.csv"
        if not path.is_file():
            raise SystemExit(f"Falta el CSV {path}. Corre `make data` primero.")
        tables[table] = read_rows(path)
    return tables


def _query_one(client, sql: str) -> dict:
    job = client.query(sql, location=LOCATION)
    return dict(next(iter(job.result())))


def _observed_from_bq(client, project: str) -> dict:
    conteos = {}
    for table in GOLD_ORDER:
        conteos[table] = int(
            _query_one(
                client,
                f"SELECT COUNT(*) AS n FROM `{project}.{GOLD_DATASET}.{table}`",
            )["n"]
        )
    avance = _query_one(
        client,
        "SELECT "
        "SUM(monto_ejecutado) AS monto_ejecutado, "
        "SUM(monto_programado) AS monto_programado "
        f"FROM `{project}.{GOLD_DATASET}.f_avance_partida`",
    )
    avance_01 = _query_one(
        client,
        "SELECT SUM(monto_ejecutado) AS ejec, SUM(monto_programado) AS prog "
        f"FROM `{project}.{GOLD_DATASET}.f_avance_partida` "
        "WHERE obra_id = 'OBR-01'",
    )
    contrato = _query_one(
        client,
        "SELECT SUM(monto_contrato) AS monto_contrato "
        f"FROM `{project}.{GOLD_DATASET}.d_partida`",
    )
    contrato_01 = _query_one(
        client,
        "SELECT SUM(monto_contrato) AS monto "
        f"FROM `{project}.{GOLD_DATASET}.d_partida` WHERE obra_id = 'OBR-01'",
    )
    asfalto = _query_one(
        client,
        "SELECT SUM(monto_real) AS real, SUM(monto_presupuestado) AS presup "
        f"FROM `{project}.{GOLD_DATASET}.f_consumo_material` "
        "WHERE obra_id = 'OBR-05' AND material_id = 'MAT-ASF'",
    )
    hh = _query_one(
        client,
        "SELECT SUM(parte.hh) AS hh, SUM(parte.cantidad_ejecutada) AS cantidad "
        f"FROM `{project}.{GOLD_DATASET}.f_hh_cuadrilla` AS parte "
        f"JOIN `{project}.{GOLD_DATASET}.d_cuadrilla` AS cuadrilla "
        "ON parte.cuadrilla_id = cuadrilla.cuadrilla_id "
        "WHERE cuadrilla.obra_id = 'OBR-01' AND cuadrilla.especialidad = 'tierras'",
    )
    huerfanas = int(
        _query_one(
            client,
            "SELECT "
            "(SELECT COUNT(*) FROM `"
            + project
            + ".csa_gold.f_avance_partida` f "
            "LEFT JOIN `"
            + project
            + ".csa_gold.d_obra` o ON f.obra_id = o.obra_id "
            "LEFT JOIN `"
            + project
            + ".csa_gold.d_partida` p ON f.partida_id = p.partida_id "
            "WHERE o.obra_id IS NULL OR p.partida_id IS NULL OR p.obra_id != f.obra_id) "
            "+ (SELECT COUNT(*) FROM `"
            + project
            + ".csa_gold.f_hh_cuadrilla` f "
            "LEFT JOIN `"
            + project
            + ".csa_gold.d_cuadrilla` c ON f.cuadrilla_id = c.cuadrilla_id "
            "LEFT JOIN `"
            + project
            + ".csa_gold.d_partida` p ON f.partida_id = p.partida_id "
            "WHERE c.cuadrilla_id IS NULL OR c.obra_id != f.obra_id OR p.obra_id != f.obra_id) "
            "+ (SELECT COUNT(*) FROM `"
            + project
            + ".csa_gold.f_consumo_material` f "
            "LEFT JOIN `"
            + project
            + ".csa_gold.d_material` m ON f.material_id = m.material_id "
            "LEFT JOIN `"
            + project
            + ".csa_gold.d_obra` o ON f.obra_id = o.obra_id "
            "WHERE m.material_id IS NULL OR o.obra_id IS NULL) AS n",
        )["n"]
    )
    ejec = Decimal(str(avance["monto_ejecutado"]))
    prog = Decimal(str(avance["monto_programado"]))
    ejec_01 = Decimal(str(avance_01["ejec"]))
    prog_01 = Decimal(str(avance_01["prog"]))
    contrato_total = Decimal(str(contrato["monto_contrato"]))
    contrato_batros = Decimal(str(contrato_01["monto"]))
    real = Decimal(str(asfalto["real"]))
    presup = Decimal(str(asfalto["presup"]))
    return {
        "conteos": conteos,
        "huerfanas": huerfanas,
        "kpis": {
            "spi": ejec / prog,
            "avance_fisico": ejec / contrato_total,
            "spi_obr_01": ejec_01 / prog_01,
            "avance_obr_01": ejec_01 / contrato_batros,
            "desviacion_asfalto_coronel": (real - presup) / presup,
            "hh_tierras_obr_01": Decimal(str(hh["hh"])) / Decimal(str(hh["cantidad"])),
            "monto_ejecutado": ejec,
            "monto_programado": prog,
            "monto_contrato": contrato_total,
        },
    }


def _fallas(sim: dict, observed: dict | None = None) -> list[str]:
    """observed None compara la simulación contra las anclas y contra silver."""
    errores = []
    if sim["huerfanas"] != 0:
        errores.append(f"huerfanas simuladas {sim['huerfanas']}")
    for nombre, esperado in ANCLAS.items():
        if sim["kpis"][nombre] != esperado:
            errores.append(f"{nombre} sim={sim['kpis'][nombre]} ancla={esperado}")
    silver = sim["conteos_silver"]
    if sim["conteos"]["f_hh_cuadrilla"] != silver["parte_hh"]:
        errores.append("f_hh_cuadrilla no cuadra con parte_hh silver")
    if sim["conteos"]["f_avance_partida"] != silver["programa_avance"]:
        errores.append("f_avance_partida no cuadra con programa silver")
    if sim["conteos"]["f_avance_partida"] != silver["medicion_avance"]:
        errores.append("f_avance_partida no cuadra con medicion silver")
    if sim["conteos"]["f_consumo_material"] != silver["presupuesto_material"]:
        errores.append("f_consumo_material no cuadra con presupuesto silver")
    if sim["conteos"]["f_consumo_material"] != silver["vale_consumo"]:
        errores.append("f_consumo_material no cuadra con vale silver")
    if observed is None:
        return errores
    if observed["huerfanas"] != 0:
        errores.append(f"huerfanas en csa_gold {observed['huerfanas']}")
    for table, n in sim["conteos"].items():
        if int(observed["conteos"][table]) != n:
            errores.append(f"{table} bq={observed['conteos'][table]} sim={n}")
    for nombre in ("spi_obr_01", "avance_obr_01", "desviacion_asfalto_coronel", "hh_tierras_obr_01"):
        if observed["kpis"][nombre] != ANCLAS[nombre]:
            errores.append(f"{nombre} bq={observed['kpis'][nombre]} ancla={ANCLAS[nombre]}")
    return errores


def render_report(sim: dict, errores: list[str]) -> str:
    lineas = [f"{'tabla':<22} {'filas':>8}"]
    lineas.append("-" * 32)
    for table in GOLD_ORDER:
        lineas.append(f"{table:<22} {sim['conteos'][table]:8d}")
    k = sim["kpis"]
    lineas.append("")
    lineas.append(f"SPI Los Batros (OBR-01)          {q2(k['spi_obr_01'])}")
    lineas.append(f"% avance Los Batros              {q2(k['avance_obr_01'])}")
    lineas.append(f"SPI Talcahuano (OBR-02)          {q2(k['spi_obr_02'])}")
    lineas.append(f"SPI Hualpén (OBR-06)             {q2(k['spi_obr_06'])}")
    lineas.append(f"desviación asfalto Coronel       {q2(k['desviacion_asfalto_coronel'])}")
    lineas.append(f"HH/unidad tierras Los Batros     {q2(k['hh_tierras_obr_01'])}")
    lineas.append(f"HH/unidad tierras Talcahuano     {q2(k['hh_tierras_obr_02'])}")
    lineas.append(f"SPI sin filtro                   {q2(k['spi'])}")
    lineas.append(f"% avance sin filtro              {q2(k['avance_fisico'])}")
    lineas.append(f"desviación sin filtro            {q2(k['desviacion'])}")
    lineas.append(f"SUM(monto_ejecutado)             {q2(k['monto_ejecutado'])}")
    lineas.append(f"SUM(monto_programado)            {q2(k['monto_programado'])}")
    lineas.append(f"SUM(monto_contrato)              {q2(k['monto_contrato'])}")
    lineas.append(f"SUM(monto_real)                  {q2(k['monto_real'])}")
    lineas.append(f"SUM(monto_presupuestado)         {q2(k['monto_presupuestado'])}")
    lineas.append(f"SUM(hh)                          {q2(k['hh'])}")
    lineas.append(f"huerfanas                        {sim['huerfanas']}")
    if errores:
        lineas.append("")
        for error in errores:
            lineas.append(f"FALLA  {error}")
    lineas.append("RESULTADO: " + ("OK" if not errores else "FALLA"))
    return "\n".join(lineas)


def run(
    *,
    dry_run: bool = False,
    project_id: str | None = None,
    client=None,
    raw_dir: Path = RAW_DIR,
) -> int:
    sim = simular(_load_tables(raw_dir))
    observed = None
    if dry_run:
        print(f"location={LOCATION}")
        print("dry_run=True")
    else:
        project = project_id or load_project_id()
        print(f"project={project}")
        print(f"location={LOCATION}")
        bq = client if client is not None else build_client(project)
        observed = _observed_from_bq(bq, project)
    errores = _fallas(sim, observed)
    print(render_report(sim, errores))
    if errores:
        print("VERIFY FALLA: gold no cuadra con la simulación.", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verifica csa_gold contra la simulación y la historia.")
    parser.add_argument("--dry-run", action="store_true", help="Solo CSV. No consulta BigQuery.")
    args = parser.parse_args(argv)
    return run(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())

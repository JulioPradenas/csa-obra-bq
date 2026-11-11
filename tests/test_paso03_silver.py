"""Paso 3 — silver, cuarentena y la prioridad. Sin credenciales y sin BigQuery."""

from __future__ import annotations

from pathlib import Path

import pytest

import build_silver
import generar_datos
import verify_silver
from contrato import DATE_COLUMNS, MOTIVOS, NUMERIC_COLUMNS, PRIORIDAD, TABLE_ORDER
from motivos import clasificar, contar, huerfanas_en_silver
from silver_sql import render_sql

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "sql" / "silver"


def _sql_code(text: str) -> str:
    kept = []
    for line in text.splitlines():
        if line.strip().startswith("--"):
            continue
        kept.append(line)
    return "\n".join(kept).upper()


def test_cada_tabla_tiene_sql_silver_y_cuarentena():
    archivos = build_silver.sql_files()
    assert [path.name for path in archivos] == [
        f"{index:02d}_{table}.sql" for index, table in enumerate(TABLE_ORDER, start=1)
    ]
    for table, path in zip(TABLE_ORDER, archivos, strict=True):
        assert path.is_file(), path
        texto = path.read_text(encoding="utf-8")
        assert texto == render_sql(table)
        assert f"CREATE OR REPLACE TABLE `csa_silver.{table}`" in texto
        assert f"CREATE OR REPLACE TABLE `csa_silver.q_{table}`" in texto
        assert PRIORIDAD in texto
        assert texto.count("CREATE OR REPLACE TABLE") == 2
        codigo = _sql_code(texto)
        for prohibido in ("INSERT", "UPDATE", "DELETE", "MERGE", "ALTER"):
            assert prohibido not in codigo
        cursor = 0
        for motivo in MOTIVOS:
            hallado = texto.find(f"'{motivo}'", cursor)
            assert hallado >= cursor, motivo
            cursor = hallado + 1
        assert "WHEN ranked.motivo_base IS NOT NULL THEN ranked.motivo_base" in texto
        assert "WHEN ranked.rn > 1 THEN 'duplicado'" in texto
        if DATE_COLUMNS.get(table) or NUMERIC_COLUMNS.get(table):
            assert "SAFE_CAST" in texto


def test_orden_de_archivos_respeta_las_fk():
    nombres = [path.name for path in build_silver.sql_files()]
    assert nombres.index("01_obras.sql") < nombres.index("03_partidas.sql")
    assert nombres.index("02_proveedores.sql") < nombres.index("05_materiales.sql")
    assert nombres.index("03_partidas.sql") < nombres.index("06_programa_avance.sql")
    assert nombres.index("04_cuadrillas.sql") < nombres.index("08_parte_hh.sql")


def test_simulacion_reproduce_el_manifiesto():
    """La prioridad del paso 2 ya cuenta el motivo ganador. No hay que recontar."""
    generado = generar_datos.generate(42)
    motives = clasificar(generado.tables)
    assert contar(motives) == generado.manifest["anomalies"]
    assert huerfanas_en_silver(generado.tables, motives) == 0
    for table in TABLE_ORDER:
        labels = motives[table]
        silver = sum(1 for label in labels if label is None)
        cuarentena = len(labels) - silver
        assert silver == generado.manifest["clean_counts"][table]
        assert cuarentena == sum(generado.manifest["anomalies"][table].values())
        assert silver + cuarentena == generado.manifest["row_counts"][table]


def test_dos_defectos_en_la_misma_fila_ganan_el_cast():
    from motivos import clasificar as clasificar_filas

    tablas = {table: [] for table in TABLE_ORDER}
    tablas["obras"] = [
        {
            "obra_id": "",
            "obra_nombre": "combo",
            "comuna": "Concepción",
            "mandante": "Mandante Sur SpA",
            "tipo_obra": "pavimentacion",
            "estado_obra": "en_ejecucion",
            "fecha_inicio": "NO-CAST",
            "fecha_termino": "2026-11-27",
            "activo": "true",
        }
    ]
    for table in TABLE_ORDER:
        if table != "obras":
            tablas[table] = []
    motives = clasificar_filas(tablas)
    assert motives["obras"] == ["cast_fallido"]


def test_verify_dry_run_sobre_csv(tmp_path: Path):
    bundle = generar_datos.generate(42)
    raw = tmp_path / "raw"
    manifest = tmp_path / "manifest.json"
    generar_datos.write_outputs(bundle, raw, manifest)
    assert verify_silver.run(dry_run=True, manifest_path=manifest, raw_dir=raw) == 0


def test_verify_report_marca_falla_si_el_motivo_no_cuadra():
    bundle = generar_datos.generate(42)
    observed = verify_silver._observed_from_frames(bundle.tables)
    text, ok = verify_silver.render_report(bundle.manifest, observed)
    assert ok
    assert "RESULTADO: OK" in text
    assert "huerfanas_en_silver 0" in text
    malo = dict(bundle.manifest)
    malo["anomalies"] = {
        table: dict(motivos) for table, motivos in bundle.manifest["anomalies"].items()
    }
    malo["anomalies"]["obras"]["cast_fallido"] = 99
    text, ok = verify_silver.render_report(malo, observed)
    assert not ok
    assert "RESULTADO: FALLA" in text


def test_build_dry_run_no_crea_cliente(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        build_silver,
        "build_client",
        lambda _project: (_ for _ in ()).throw(AssertionError("no debe conectar")),
    )
    assert build_silver.run(dry_run=True) == 0


def test_makefile_run_incluye_silver_y_dry_en_ci():
    texto = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "build_silver.py" in texto
    assert "verify_silver.py" in texto
    assert "ifeq ($(CI),true)" in texto
    assert "DRY ?= 1" in texto
    run = texto.split("run:", 1)[1]
    assert "silver" in run.split("\n", 1)[0]

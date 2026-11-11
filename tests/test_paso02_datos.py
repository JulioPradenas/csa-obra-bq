"""Paso 2 — semilla estable, suciedad contada y manifest = CSV. Sin GCP."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import generar_datos
from contrato import MOTIVOS, TABLE_ORDER, columns
from csv_io import csv_path, read_rows, write_table
from motivos import clasificar, contar

ROOT = Path(__file__).resolve().parents[1]


def test_semilla_estable_dos_corridas():
    primera = generar_datos.generate(42)
    segunda = generar_datos.generate(42)
    assert primera.manifest == segunda.manifest
    for table in TABLE_ORDER:
        cols = columns(table)
        filas_a = [tuple(row[col] for col in cols) for row in primera.tables[table]]
        filas_b = [tuple(row[col] for col in cols) for row in segunda.tables[table]]
        assert filas_a == filas_b


def test_otra_semilla_cambia_el_csv():
    base = generar_datos.generate(42)
    otra = generar_datos.generate(99)
    assert base.manifest["row_counts"] == otra.manifest["row_counts"]
    assert base.tables["programa_avance"] != otra.tables["programa_avance"]


def test_csv_dos_escrituras_identicas(tmp_path: Path):
    gen_a = generar_datos.generate(42)
    gen_b = generar_datos.generate(42)
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    for folder, gen in ((dir_a, gen_a), (dir_b, gen_b)):
        folder.mkdir()
        for table in TABLE_ORDER:
            write_table(csv_path(folder, table), table, gen.tables[table])
    for table in TABLE_ORDER:
        assert csv_path(dir_a, table).read_bytes() == csv_path(dir_b, table).read_bytes()


def test_manifest_cuadra_con_los_csv_y_la_prioridad(tmp_path: Path):
    generado = generar_datos.generate(42)
    for table in TABLE_ORDER:
        write_table(csv_path(tmp_path, table), table, generado.tables[table])
        filas = read_rows(csv_path(tmp_path, table))
        assert list(filas[0]) == columns(table)
        assert len(filas) == generado.manifest["row_counts"][table]

    motives = clasificar(generado.tables)
    assert contar(motives) == generado.manifest["anomalies"]
    for table in TABLE_ORDER:
        extra = sum(generado.manifest["anomalies"][table][motivo] for motivo in MOTIVOS)
        assert generado.manifest["row_counts"][table] == (
            generado.manifest["clean_counts"][table] + extra
        )
        assert set(generado.manifest["anomalies"][table]) == set(MOTIVOS)

    committed = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
    assert committed == generado.manifest


def test_historia_spi_bajo_y_sobreconsumo():
    generado = generar_datos.generate(42)
    motives = clasificar(generado.tables)
    tables = generado.tables

    spi_atrasada = generar_datos._spi(tables, motives, "OBR-01")
    spi_al_dia = generar_datos._spi(tables, motives, "OBR-02")
    spi_paralizada = generar_datos._spi(tables, motives, "OBR-06")
    assert spi_paralizada == Decimal("0.55")
    assert spi_atrasada == Decimal("0.70")
    assert spi_al_dia == Decimal("1.05")
    assert spi_atrasada < Decimal("0.80") < spi_al_dia

    avance = generar_datos._avance_fisico(tables, motives, "OBR-01")
    assert avance == Decimal("0.56")
    assert avance != spi_atrasada

    desviacion = generar_datos._desviacion(tables, motives, "OBR-05", "MAT-ASF")
    assert desviacion == Decimal("0.40")
    assert generar_datos._desviacion(tables, motives, "OBR-05", "MAT-CEM") == Decimal("0")

    hh_lenta = generar_datos._hh_por_unidad(tables, motives, "OBR-01", "tierras")
    hh_al_dia = generar_datos._hh_por_unidad(tables, motives, "OBR-02", "tierras")
    assert hh_lenta == Decimal("1.40")
    assert hh_al_dia == Decimal("0.80")


def test_fila_con_cast_y_nulo_gana_el_cast():
    generado = generar_datos.generate(42)
    motives = clasificar(generado.tables)
    encontradas = [
        (row, motivo)
        for row, motivo in zip(generado.tables["obras"], motives["obras"], strict=True)
        if row["obra_nombre"] == "Fila con cast y clave vacía"
    ]
    assert len(encontradas) == 1
    row, motivo = encontradas[0]
    assert row["obra_id"] == ""
    assert row["fecha_inicio"] == "NO-CAST"
    assert motivo == "cast_fallido"


def test_suciedad_visible_en_el_csv():
    generado = generar_datos.generate(42)
    textos = []
    for rows in generado.tables.values():
        for row in rows:
            textos.extend(row.values())
    unidos = "\n".join(textos)
    for token in (
        "NO-CAST",
        "12,5",
        "2026-02-31",
        "2026-05-06",
        "OBR-HUERFANA",
        "PAR-HUERFANA",
        "CUA-HUERFANA",
        "MAT-HUERFANA",
        "PRV-HUERFANO",
        "demolicion",
        "SI",
    ):
        assert token in unidos, token
    assert generado.manifest["anomalies"]["obras"]["fk_huerfana"] == 0
    assert generado.manifest["anomalies"]["proveedores"]["fecha_incoherente"] == 0
    assert generado.manifest["anomalies"]["partidas"]["fecha_incoherente"] == 0

"""Paso 4 — gold, CLUSTER BY y la historia. Sin credenciales y sin BigQuery."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

import build_gold
import generar_datos
import verify_gold
from gold_sim import GOLD_ORDER, simular

ROOT = Path(__file__).resolve().parents[1]


def _sql_code(text: str) -> str:
    kept = []
    for line in text.splitlines():
        if line.strip().startswith("--"):
            continue
        kept.append(line)
    return "\n".join(kept).upper()


def test_sql_gold_tiene_cluster_y_no_particion():
    archivos = build_gold.sql_files()
    assert len(archivos) == 9
    assert all(path.is_file() for path in archivos)
    vistos = set()
    for path in archivos:
        codigo = _sql_code(path.read_text(encoding="utf-8"))
        assert "CREATE OR REPLACE TABLE" in codigo
        assert "CLUSTER BY" in codigo
        assert "PARTITION BY" not in codigo
        for prohibido in ("INSERT", "UPDATE", "DELETE", "MERGE", "ALTER"):
            assert prohibido not in codigo
        assert "INTERVAL 60 DAY" in codigo
        for table in GOLD_ORDER:
            if f"`CSA_GOLD.{table.upper()}`" in codigo:
                vistos.add(table)
                if table.startswith("f_") or table == "d_obra":
                    assert "CLUSTER BY OBRA_ID" in codigo
    assert vistos == set(GOLD_ORDER)


def test_grano_escrito_en_los_hechos():
    textos = {
        path.name: path.read_text(encoding="utf-8") for path in build_gold.sql_files()
    }
    assert "obra × partida × semana" in textos["07_f_avance_partida.sql"]
    assert "obra × cuadrilla × día" in textos["08_f_hh_cuadrilla.sql"]
    assert "obra × material × semana" in textos["09_f_consumo_material.sql"]
    avance = textos["07_f_avance_partida.sql"]
    assert "monto_programado" in avance and "monto_ejecutado" in avance
    assert "AS spi" not in avance.lower()
    assert "hh / cantidad" not in textos["08_f_hh_cuadrilla.sql"]


def test_simulacion_reproduce_la_historia_y_los_conteos():
    sim = simular(generar_datos.generate(42).tables)
    assert sim["huerfanas"] == 0
    assert sim["conteos"] == {
        "d_obra": 7,
        "d_proveedor": 5,
        "d_partida": 35,
        "d_cuadrilla": 14,
        "d_material": 6,
        "d_fecha": 208,
        "f_avance_partida": 735,
        "f_hh_cuadrilla": 1470,
        "f_consumo_material": 882,
    }
    assert verify_gold._fallas(sim) == []
    k = sim["kpis"]
    assert k["spi_obr_01"] == Decimal("0.70")
    assert k["desviacion_asfalto_coronel"] == Decimal("0.40")
    assert k["monto_ejecutado"] == Decimal("4941031200.00")
    assert k["monto_programado"] == Decimal("5503260000.00")
    assert k["monto_contrato"] == Decimal("6879075000.00")


def test_guia_publica_los_valores_sin_filtro():
    texto = (ROOT / "looker" / "STYLE_GUIDE.md").read_text(encoding="utf-8")
    for pieza in (
        "Lab de portafolio. Marca con fines ilustrativos.",
        "4.941.031.200",
        "5.503.260.000",
        "6.879.075.000",
        "0,70",
        "0,40",
        "Resumen de obras",
        "Avance vs programa",
        "Productividad HH",
        "Materiales y desviación",
        "% avance físico = SUM(monto_ejecutado) / SUM(monto_contrato)",
        "SPI = SUM(monto_ejecutado) / SUM(monto_programado)",
        "nunca como promedio de porcentajes",
    ):
        assert pieza in texto, pieza


def test_verify_dry_run(tmp_path: Path):
    bundle = generar_datos.generate(42)
    raw = tmp_path / "raw"
    generar_datos.write_outputs(bundle, raw, tmp_path / "manifest.json")
    assert verify_gold.run(dry_run=True, raw_dir=raw) == 0


def test_build_dry_run_no_crea_cliente(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        build_gold,
        "build_client",
        lambda _project: (_ for _ in ()).throw(AssertionError("no debe conectar")),
    )
    assert build_gold.run(dry_run=True) == 0


def test_makefile_run_incluye_gold():
    texto = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "build_gold.py" in texto
    assert "verify_gold.py" in texto
    assert "ifeq ($(CI),true)" in texto
    assert "DRY ?= 1" in texto
    primera = texto.split("run:", 1)[1].split("\n", 1)[0]
    assert "gold" in primera
    assert "silver" in primera

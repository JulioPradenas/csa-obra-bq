"""Paso 5 — vistas planas para Looker Studio. Sin credenciales y sin BigQuery."""

from __future__ import annotations

import re
from collections import defaultdict
from decimal import Decimal

import build_looker_views
import generar_datos
from gold_sim import simular


def _code(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not line.strip().startswith("--"))


def test_tres_vistas_create_or_replace_view_en_gold():
    archivos = build_looker_views.sql_files()
    assert len(archivos) == 3
    assert all(path.is_file() for path in archivos)
    stmts = build_looker_views.statements()
    assert len(stmts) == 3
    for _, stmt in stmts:
        assert stmt.upper().startswith("CREATE OR REPLACE VIEW `CSA_GOLD.V_")
        assert "INSERT" not in stmt.upper() and "MERGE" not in stmt.upper()


def test_vistas_leen_solo_gold():
    for path in build_looker_views.sql_files():
        refs = re.findall(r"`([a-z_]+)\.", _code(path.read_text(encoding="utf-8")))
        assert refs and set(refs) == {"csa_gold"}, path.name


def test_dry_run_no_llama_a_bigquery(capsys):
    assert build_looker_views.run(dry_run=True) == 0
    assert "dry-run" in capsys.readouterr().out


def test_contrato_en_la_primera_semana_reproduce_el_avance():
    """La vista pone monto_contrato solo en la primera semana de cada partida."""
    sim = simular(generar_datos.generate(42).tables)
    partidas = {p["partida_id"]: p for p in sim["dims"]["d_partida"]}
    filas = sim["hechos"]["f_avance_partida"]
    primera = defaultdict(lambda: None)
    for fila in filas:
        clave = (fila["obra_id"], fila["partida_id"])
        if primera[clave] is None or fila["semana_lunes"] < primera[clave]:
            primera[clave] = fila["semana_lunes"]
    contrato = Decimal(0)
    for fila in filas:
        if fila["semana_lunes"] == primera[(fila["obra_id"], fila["partida_id"])]:
            contrato += partidas[fila["partida_id"]]["monto_contrato"]
    ejecutado = sum(fila["monto_ejecutado"] for fila in filas)
    assert contrato == Decimal("6879075000.00")
    assert round(ejecutado / contrato, 4) == Decimal("0.7183")


def test_controles_coinciden_con_los_esperados_de_gold():
    sim = simular(generar_datos.generate(42).tables)
    kpis = sim["kpis"]
    esperados = {nombre: valor for nombre, _, valor, _ in build_looker_views.CHECKS}
    assert round(kpis["spi"], 4) == esperados["SPI sin filtro"]
    assert round(kpis["avance_fisico"], 4) == esperados["% avance físico sin filtro"]
    assert round(kpis["desviacion"], 4) == esperados["desviación sin filtro"]
    assert kpis["hh"] == esperados["SUM(hh)"]

"""Prioridad de cuarentena sobre el CSV crudo. La misma regla la usará silver.

cast_fallido > nulo_obligatorio > duplicado > fk_huerfana > fecha_incoherente

Una fila sale una vez. El duplicado y la FK se miran solo entre filas que ya
pasaron el cast y los nulos. La FK se resuelve contra el padre que quedó en
silver, no contra bronze.
"""

from __future__ import annotations

import re
from datetime import datetime

from contrato import (
    BOOL_COLUMNS,
    BOOL_OK,
    CATALOG_COLUMNS,
    CATALOGS,
    DATE_COLUMNS,
    FK_RULES,
    MOTIVOS,
    NATURAL_KEY,
    NUMERIC_COLUMNS,
    TABLE_ORDER,
    required_columns,
)

_NUMERO = re.compile(r"^\d+(\.\d+)?$")
_FECHA = "%Y-%m-%d"


def _vacio(value: str) -> bool:
    return value.strip() == ""


def _fecha(value: str) -> datetime | None:
    try:
        return datetime.strptime(value.strip(), _FECHA)
    except ValueError:
        return None


def _cast_fallido(table: str, row: dict[str, str]) -> bool:
    for column in DATE_COLUMNS.get(table, ()):
        text = row.get(column, "")
        if _vacio(text):
            continue
        if _fecha(text) is None:
            return True
    for column in NUMERIC_COLUMNS.get(table, ()):
        text = row.get(column, "")
        if _vacio(text):
            continue
        if _NUMERO.fullmatch(text.strip()) is None:
            return True
    for column in BOOL_COLUMNS.get(table, ()):
        text = row.get(column, "")
        if _vacio(text):
            continue
        if text.strip() not in BOOL_OK:
            return True
    for column in CATALOG_COLUMNS.get(table, ()):
        text = row.get(column, "")
        if _vacio(text):
            continue
        if text.strip() not in CATALOGS[column]:
            return True
    return False


def _nulo(table: str, row: dict[str, str]) -> bool:
    return any(_vacio(row.get(column, "")) for column in required_columns(table))


def _fecha_incoherente(
    table: str,
    row: dict[str, str],
    silver: dict[str, dict[str, dict[str, str]]],
) -> bool:
    if table == "obras":
        inicio = _fecha(row["fecha_inicio"])
        termino = _fecha(row["fecha_termino"])
        if inicio is None or termino is None:
            return False
        return termino < inicio

    if table in {"programa_avance", "medicion_avance", "presupuesto_material", "vale_consumo"}:
        dia = _fecha(row["semana_lunes"])
        if dia is None:
            return False
        if dia.weekday() != 0:
            return True
        obra = silver["obras"].get(row["obra_id"])
        if obra is None:
            return False
        inicio = _fecha(obra["fecha_inicio"])
        termino = _fecha(obra["fecha_termino"])
        if inicio is None or termino is None:
            return False
        return dia < inicio or dia > termino

    if table == "parte_hh":
        dia = _fecha(row["fecha"])
        if dia is None:
            return False
        obra = silver["obras"].get(row["obra_id"])
        if obra is None:
            return False
        inicio = _fecha(obra["fecha_inicio"])
        termino = _fecha(obra["fecha_termino"])
        if inicio is None or termino is None:
            return False
        return dia < inicio or dia > termino

    return False


def _fk_huerfana(
    table: str,
    row: dict[str, str],
    silver: dict[str, dict[str, dict[str, str]]],
) -> bool:
    for column, parent_table, _parent_pk, misma_obra in FK_RULES.get(table, ()):
        parent = silver[parent_table].get(row[column])
        if parent is None:
            return True
        if misma_obra is not None and parent[misma_obra] != row[misma_obra]:
            return True
    return False


def clasificar(
    tables: dict[str, list[dict[str, str]]],
) -> dict[str, list[str | None]]:
    """None = la fila se queda en silver. Si no, el motivo ganador."""
    motives: dict[str, list[str | None]] = {}
    silver: dict[str, dict[str, dict[str, str]]] = {table: {} for table in TABLE_ORDER}

    for table in TABLE_ORDER:
        rows = tables[table]
        first: list[str | None] = []
        for row in rows:
            if _cast_fallido(table, row):
                first.append("cast_fallido")
            elif _nulo(table, row):
                first.append("nulo_obligatorio")
            else:
                first.append(None)

        seen: dict[tuple[str, ...], int] = {}
        kept_index: list[int] = []
        for index, row in enumerate(rows):
            if first[index] is not None:
                continue
            key = tuple(row[column] for column in NATURAL_KEY[table])
            if key in seen:
                first[index] = "duplicado"
            else:
                seen[key] = index
                kept_index.append(index)

        for index in kept_index:
            row = rows[index]
            if _fk_huerfana(table, row, silver):
                first[index] = "fk_huerfana"
            elif _fecha_incoherente(table, row, silver):
                first[index] = "fecha_incoherente"
            else:
                # Solo las dimensiones son padres. Los hechos no se consultan por FK.
                if len(NATURAL_KEY[table]) == 1:
                    silver[table][row[NATURAL_KEY[table][0]]] = row

        motives[table] = first
    return motives


def contar(motives: dict[str, list[str | None]]) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for table, labels in motives.items():
        bucket = {motivo: 0 for motivo in MOTIVOS}
        for label in labels:
            if label is not None:
                bucket[label] += 1
        counts[table] = bucket
    return counts

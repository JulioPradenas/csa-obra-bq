"""Contrato bronze. El DDL se renderiza desde aquí. Todo STRING NULLABLE."""

from __future__ import annotations

from bq_env import DATASET, EXPIRATION_DAYS, NOTICE

TABLE_ORDER: tuple[str, ...] = (
    "obras",
    "proveedores",
    "partidas",
    "cuadrillas",
    "materiales",
    "programa_avance",
    "medicion_avance",
    "parte_hh",
    "presupuesto_material",
    "vale_consumo",
)

TABLES: dict[str, list[tuple[str, str]]] = {
    "obras": [
        ("obra_id", "STRING"),
        ("obra_nombre", "STRING"),
        ("comuna", "STRING"),
        ("mandante", "STRING"),
        ("tipo_obra", "STRING"),
        ("estado_obra", "STRING"),
        ("fecha_inicio", "STRING"),
        ("fecha_termino", "STRING"),
        ("activo", "STRING"),
    ],
    "proveedores": [
        ("proveedor_id", "STRING"),
        ("proveedor_nombre", "STRING"),
        ("rubro", "STRING"),
        ("comuna", "STRING"),
        ("activo", "STRING"),
    ],
    "partidas": [
        ("partida_id", "STRING"),
        ("obra_id", "STRING"),
        ("codigo_partida", "STRING"),
        ("partida_nombre", "STRING"),
        ("capitulo", "STRING"),
        ("unidad_medida", "STRING"),
        ("cantidad_contrato", "STRING"),
        ("precio_unitario", "STRING"),
        ("hh_teorica_por_unidad", "STRING"),
    ],
    "cuadrillas": [
        ("cuadrilla_id", "STRING"),
        ("cuadrilla_nombre", "STRING"),
        ("especialidad", "STRING"),
        ("obra_id", "STRING"),
        ("activo", "STRING"),
    ],
    "materiales": [
        ("material_id", "STRING"),
        ("material_nombre", "STRING"),
        ("familia", "STRING"),
        ("unidad_medida", "STRING"),
        ("precio_unitario", "STRING"),
        ("proveedor_id", "STRING"),
    ],
    "programa_avance": [
        ("programa_id", "STRING"),
        ("obra_id", "STRING"),
        ("partida_id", "STRING"),
        ("semana_lunes", "STRING"),
        ("cantidad_programada", "STRING"),
    ],
    "medicion_avance": [
        ("medicion_id", "STRING"),
        ("obra_id", "STRING"),
        ("partida_id", "STRING"),
        ("semana_lunes", "STRING"),
        ("cantidad_ejecutada", "STRING"),
    ],
    "parte_hh": [
        ("parte_id", "STRING"),
        ("obra_id", "STRING"),
        ("cuadrilla_id", "STRING"),
        ("partida_id", "STRING"),
        ("fecha", "STRING"),
        ("hh", "STRING"),
        ("cantidad_ejecutada", "STRING"),
    ],
    "presupuesto_material": [
        ("presupuesto_id", "STRING"),
        ("obra_id", "STRING"),
        ("material_id", "STRING"),
        ("semana_lunes", "STRING"),
        ("cantidad_presupuestada", "STRING"),
    ],
    "vale_consumo": [
        ("vale_id", "STRING"),
        ("obra_id", "STRING"),
        ("material_id", "STRING"),
        ("semana_lunes", "STRING"),
        ("cantidad_real", "STRING"),
    ],
}

# hh_teorica_por_unidad es el único opcional. Vacío sigue en silver.
OPTIONAL: dict[str, frozenset[str]] = {
    "partidas": frozenset({"hh_teorica_por_unidad"}),
}

NATURAL_KEY: dict[str, tuple[str, ...]] = {
    "obras": ("obra_id",),
    "proveedores": ("proveedor_id",),
    "partidas": ("partida_id",),
    "cuadrillas": ("cuadrilla_id",),
    "materiales": ("material_id",),
    "programa_avance": ("obra_id", "partida_id", "semana_lunes"),
    "medicion_avance": ("obra_id", "partida_id", "semana_lunes"),
    "parte_hh": ("obra_id", "cuadrilla_id", "fecha"),
    "presupuesto_material": ("obra_id", "material_id", "semana_lunes"),
    "vale_consumo": ("obra_id", "material_id", "semana_lunes"),
}

CATALOGS: dict[str, frozenset[str]] = {
    "tipo_obra": frozenset({"pavimentacion", "conservacion", "puente", "aguas_lluvia"}),
    "estado_obra": frozenset({"en_ejecucion", "paralizada", "terminada"}),
    "capitulo": frozenset(
        {"movimiento_tierras", "pavimentos", "obras_arte", "senalizacion", "drenaje"}
    ),
    "especialidad": frozenset({"tierras", "pavimento", "estructuras", "senalizacion"}),
    "rubro": frozenset({"cemento", "arido", "asfalto", "acero", "combustible"}),
    "familia": frozenset({"cemento", "arido", "asfalto", "acero", "combustible"}),
    "unidad_medida": frozenset({"m3", "m2", "ml", "kg", "ton", "l", "un"}),
}

CATALOG_COLUMNS: dict[str, tuple[str, ...]] = {
    "obras": ("tipo_obra", "estado_obra"),
    "proveedores": ("rubro",),
    "partidas": ("capitulo", "unidad_medida"),
    "cuadrillas": ("especialidad",),
    "materiales": ("familia", "unidad_medida"),
}

DATE_COLUMNS: dict[str, tuple[str, ...]] = {
    "obras": ("fecha_inicio", "fecha_termino"),
    "programa_avance": ("semana_lunes",),
    "medicion_avance": ("semana_lunes",),
    "parte_hh": ("fecha",),
    "presupuesto_material": ("semana_lunes",),
    "vale_consumo": ("semana_lunes",),
}

NUMERIC_COLUMNS: dict[str, tuple[str, ...]] = {
    "partidas": ("cantidad_contrato", "precio_unitario", "hh_teorica_por_unidad"),
    "materiales": ("precio_unitario",),
    "programa_avance": ("cantidad_programada",),
    "medicion_avance": ("cantidad_ejecutada",),
    "parte_hh": ("hh", "cantidad_ejecutada"),
    "presupuesto_material": ("cantidad_presupuestada",),
    "vale_consumo": ("cantidad_real",),
}

BOOL_COLUMNS: dict[str, tuple[str, ...]] = {
    "obras": ("activo",),
    "proveedores": ("activo",),
    "cuadrillas": ("activo",),
}

# (columna en la fila, tabla padre, pk del padre, columna de la fila que debe
# coincidir con la misma columna del padre). La última es None si basta con que
# el id exista. Si el id existe y la obra no calza, también es fk_huerfana.
FK_RULES: dict[str, tuple[tuple[str, str, str, str | None], ...]] = {
    "partidas": (("obra_id", "obras", "obra_id", None),),
    "cuadrillas": (("obra_id", "obras", "obra_id", None),),
    "materiales": (("proveedor_id", "proveedores", "proveedor_id", None),),
    "programa_avance": (
        ("obra_id", "obras", "obra_id", None),
        ("partida_id", "partidas", "partida_id", "obra_id"),
    ),
    "medicion_avance": (
        ("obra_id", "obras", "obra_id", None),
        ("partida_id", "partidas", "partida_id", "obra_id"),
    ),
    "parte_hh": (
        ("obra_id", "obras", "obra_id", None),
        ("cuadrilla_id", "cuadrillas", "cuadrilla_id", "obra_id"),
        ("partida_id", "partidas", "partida_id", "obra_id"),
    ),
    "presupuesto_material": (
        ("obra_id", "obras", "obra_id", None),
        ("material_id", "materiales", "material_id", None),
    ),
    "vale_consumo": (
        ("obra_id", "obras", "obra_id", None),
        ("material_id", "materiales", "material_id", None),
    ),
}

MOTIVOS: tuple[str, ...] = (
    "cast_fallido",
    "nulo_obligatorio",
    "duplicado",
    "fk_huerfana",
    "fecha_incoherente",
)

PRIORIDAD = "cast_fallido > nulo_obligatorio > duplicado > fk_huerfana > fecha_incoherente"

BOOL_OK = frozenset({"true", "True", "1", "false", "False", "0"})


def columns(table: str) -> list[str]:
    return [name for name, _typ in TABLES[table]]


def required_columns(table: str) -> tuple[str, ...]:
    optional = OPTIONAL.get(table, frozenset())
    return tuple(name for name in columns(table) if name not in optional)


def render_ddl() -> str:
    """CREATE OR REPLACE. Bronze es todo STRING NULLABLE. El tipo vive en silver."""
    header = f"""-- CSA Obra — DDL bronze (landing crudo, todo STRING NULLABLE).
-- Dataset: {DATASET} · location: US · expiración: {EXPIRATION_DAYS} días.
-- Sandbox sin facturación: sin DML y sin streaming. Este archivo solo tiene
-- CREATE OR REPLACE TABLE. Los CSV entran por load job WRITE_TRUNCATE
-- con max_bad_records=0. No hay ALTER.
--
-- Todas las columnas son STRING. Un BOOL/DATE/TIMESTAMP en el load rechaza
-- el token 'NO-CAST' y el job falla entero (incidente de Meli). Silver
-- castea con SAFE_CAST.
--
-- {NOTICE}
"""
    blocks: list[str] = [header.rstrip(), ""]
    for table in TABLE_ORDER:
        col_sql = ",\n".join(f"  {name} {typ}" for name, typ in TABLES[table])
        desc = (
            f"Bronze {table}. {NOTICE} "
            "Landing NULLABLE; la tabla expira a los 60 días."
        )
        blocks.append(
            "CREATE OR REPLACE TABLE "
            f"`{DATASET}.{table}` (\n"
            f"{col_sql}\n"
            ")\n"
            "OPTIONS (\n"
            f'  description="{desc}",\n'
            "  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)\n"
            ");\n"
        )
    return "\n".join(blocks).rstrip() + "\n"

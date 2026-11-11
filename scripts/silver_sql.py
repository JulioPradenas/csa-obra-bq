"""SQL de silver y cuarentena. Misma prioridad que scripts/motivos.py.

cast_fallido > nulo_obligatorio > duplicado > fk_huerfana > fecha_incoherente

Cada archivo hace dos CREATE OR REPLACE: la tabla tipada y q_<tabla> con la
fila cruda en STRING, un motivo y la regla. Sin DML.
"""

from __future__ import annotations

from contrato import (
    BOOL_COLUMNS,
    BOOL_OK,
    CATALOG_COLUMNS,
    CATALOGS,
    DATE_COLUMNS,
    EXPIRATION_DAYS,
    FK_RULES,
    MOTIVOS,
    NATURAL_KEY,
    NOTICE,
    NUMERIC_COLUMNS,
    PRIORIDAD,
    TABLE_ORDER,
    columns,
    required_columns,
)
from bq_env import EXPIRATION_DAYS as _EXP_DAYS
from bq_env import NOTICE as _NOTICE
from bq_env import SILVER_DATASET

# Reexportados para que el SQL y el contrato no se desfasen.
assert EXPIRATION_DAYS == _EXP_DAYS
assert NOTICE == _NOTICE

BRONZE_DATASET = "csa_bronze"


def sql_filename(table: str, index: int) -> str:
    return f"{index:02d}_{table}.sql"


def silver_type(table: str, column: str) -> str:
    if column in DATE_COLUMNS.get(table, ()):
        return "DATE"
    if column in NUMERIC_COLUMNS.get(table, ()):
        return "NUMERIC"
    if column in BOOL_COLUMNS.get(table, ()):
        return "BOOL"
    return "STRING"


def _trimmed(column: str) -> str:
    return f"NULLIF(TRIM(CAST(src.{column} AS STRING)), '')"


def _typed_expr(table: str, column: str) -> str:
    trimmed = _trimmed(column)
    if column in DATE_COLUMNS.get(table, ()) or column in NUMERIC_COLUMNS.get(table, ()):
        kind = silver_type(table, column)
        return f"SAFE_CAST({trimmed} AS {kind})"
    if column in BOOL_COLUMNS.get(table, ()):
        ok_true = ", ".join(repr(token) for token in ("true", "True", "1"))
        ok_false = ", ".join(repr(token) for token in ("false", "False", "0"))
        return (
            "CASE\n"
            f"        WHEN {trimmed} IS NULL THEN NULL\n"
            f"        WHEN TRIM(CAST(src.{column} AS STRING)) IN ({ok_true}) THEN TRUE\n"
            f"        WHEN TRIM(CAST(src.{column} AS STRING)) IN ({ok_false}) THEN FALSE\n"
            "        ELSE NULL\n"
            "      END"
        )
    if column in CATALOG_COLUMNS.get(table, ()):
        return f"NULLIF(LOWER(TRIM(CAST(src.{column} AS STRING))), '')"
    if column.endswith("_id"):
        return f"NULLIF(UPPER(TRIM(CAST(src.{column} AS STRING))), '')"
    return trimmed


def _cast_flag(table: str, column: str) -> str | None:
    trimmed = _trimmed(column)
    if column in DATE_COLUMNS.get(table, ()) or column in NUMERIC_COLUMNS.get(table, ()):
        kind = silver_type(table, column)
        return f"({trimmed} IS NOT NULL AND SAFE_CAST({trimmed} AS {kind}) IS NULL)"
    if column in BOOL_COLUMNS.get(table, ()):
        tokens = ", ".join(repr(token) for token in sorted(BOOL_OK))
        return (
            f"({trimmed} IS NOT NULL AND TRIM(CAST(src.{column} AS STRING)) NOT IN ({tokens}))"
        )
    if column in CATALOG_COLUMNS.get(table, ()):
        allowed = ", ".join(repr(code) for code in sorted(CATALOGS[column]))
        return (
            f"({trimmed} IS NOT NULL AND LOWER(TRIM(CAST(src.{column} AS STRING))) "
            f"NOT IN ({allowed}))"
        )
    return None


def _parent_alias(parent: str) -> str:
    return f"dim_{parent}"


def _fk_predicates(table: str) -> list[tuple[str, str]]:
    """(condicion SQL, regla) en el orden de FK_RULES."""
    out: list[tuple[str, str]] = []
    for column, parent, parent_pk, misma_obra in FK_RULES.get(table, ()):
        alias = _parent_alias(parent)
        out.append((f"{alias}.{parent_pk} IS NULL", column))
        if misma_obra is not None:
            out.append((f"{alias}.{misma_obra} != ranked.{misma_obra}", column))
    return out


def _fecha_predicates(table: str) -> list[tuple[str, str]]:
    if table == "obras":
        return [("ranked.fecha_termino < ranked.fecha_inicio", "fecha_termino")]
    if table in {"programa_avance", "medicion_avance", "presupuesto_material", "vale_consumo"}:
        obra = _parent_alias("obras")
        return [
            ("EXTRACT(DAYOFWEEK FROM ranked.semana_lunes) != 2", "semana_lunes"),
            (f"ranked.semana_lunes < {obra}.fecha_inicio", "semana_lunes"),
            (f"ranked.semana_lunes > {obra}.fecha_termino", "semana_lunes"),
        ]
    if table == "parte_hh":
        obra = _parent_alias("obras")
        return [
            (f"ranked.fecha < {obra}.fecha_inicio", "fecha"),
            (f"ranked.fecha > {obra}.fecha_termino", "fecha"),
        ]
    return []


def _joins(table: str) -> str:
    parents: list[str] = []
    for _column, parent, _pk, _misma in FK_RULES.get(table, ()):
        if parent not in parents:
            parents.append(parent)
    if table in {"programa_avance", "medicion_avance", "presupuesto_material", "vale_consumo", "parte_hh"}:
        if "obras" not in parents:
            parents.append("obras")
    lines = []
    seen_on: set[tuple[str, str]] = set()
    for column, parent, parent_pk, _misma in FK_RULES.get(table, ()):
        key = (parent, column)
        if key in seen_on:
            continue
        seen_on.add(key)
        alias = _parent_alias(parent)
        lines.append(
            f"LEFT JOIN `{SILVER_DATASET}.{parent}` AS {alias}\n"
            f"    ON ranked.{column} = {alias}.{parent_pk}"
        )
    if table in {"programa_avance", "medicion_avance", "presupuesto_material", "vale_consumo", "parte_hh"}:
        if not any(parent == "obras" for parent, _column in seen_on):
            lines.append(
                f"LEFT JOIN `{SILVER_DATASET}.obras` AS dim_obras\n"
                "    ON ranked.obra_id = dim_obras.obra_id"
            )
    return "\n".join(lines)


def _partition_expr(table: str) -> str:
    parts = []
    for column in NATURAL_KEY[table]:
        kind = silver_type(table, column)
        ref = column
        if kind == "DATE":
            ref = f"CAST({column} AS STRING)"
        parts.append(f"IF(motivo_base IS NULL, {ref}, NULL)")
    return ",\n        ".join(parts)


def _order_id(table: str) -> str:
    return columns(table)[0]


def _or_join(predicates: list[str]) -> str:
    if not predicates:
        return "FALSE"
    if len(predicates) == 1:
        return predicates[0]
    return " OR ".join(f"({item})" for item in predicates)


def render_sql(table: str) -> str:
    cols = columns(table)
    cast_cols = [column for column in cols if _cast_flag(table, column)]
    fk_preds = _fk_predicates(table)
    fecha_preds = _fecha_predicates(table)
    fk_sql = _or_join([cond for cond, _regla in fk_preds]) if fk_preds else "FALSE"
    fecha_sql = _or_join([cond for cond, _regla in fecha_preds]) if fecha_preds else "FALSE"

    raw_lines = [f"    src.{column} AS raw_{column}" for column in cols]
    typed_lines = [f"    {_typed_expr(table, column)} AS {column}" for column in cols]
    flag_lines = [f"    {_cast_flag(table, column)} AS fail_{column}" for column in cast_cols]
    select_body = ",\n".join(raw_lines + typed_lines + flag_lines)

    nulo_when = " OR ".join(f"{column} IS NULL" for column in required_columns(table))
    cast_when = " OR ".join(f"fail_{column}" for column in cast_cols) if cast_cols else "FALSE"

    regla_cast = []
    for column in cast_cols:
        regla_cast.append(f"      WHEN fail_{column} THEN '{column}'")
    regla_nulo = []
    for column in required_columns(table):
        regla_nulo.append(f"      WHEN {column} IS NULL THEN '{column}'")
    regla_fk = [f"      WHEN {cond} THEN '{regla}'" for cond, regla in fk_preds]
    regla_fecha = [f"      WHEN {cond} THEN '{regla}'" for cond, regla in fecha_preds]

    def _whens(lines: list[str], fallback: str) -> str:
        if not lines:
            return f"      WHEN FALSE THEN '{fallback}'"
        return "\n".join(lines)

    motivo_case = f"""    CASE
      WHEN {cast_when} THEN 'cast_fallido'
      WHEN {nulo_when} THEN 'nulo_obligatorio'
      ELSE NULL
    END AS motivo_base"""

    regla_base = f"""    CASE
{_whens(regla_cast, 'cast')}
{_whens(regla_nulo, 'nulo')}
      ELSE NULL
    END AS regla_base"""

    joins = _joins(table)
    if joins:
        join_sql = "\n" + "\n".join(f"  {line}" for line in joins.splitlines())
    else:
        join_sql = ""

    motivo_resuelto = f"""    CASE
      WHEN ranked.motivo_base IS NOT NULL THEN ranked.motivo_base
      WHEN ranked.rn > 1 THEN 'duplicado'
      WHEN {fk_sql} THEN 'fk_huerfana'
      WHEN {fecha_sql} THEN 'fecha_incoherente'
      ELSE NULL
    END AS motivo"""

    regla_resuelta = f"""    CASE
      WHEN ranked.motivo_base IS NOT NULL THEN ranked.regla_base
      WHEN ranked.rn > 1 THEN 'llave natural'
{_whens(regla_fk, 'fk')}
{_whens(regla_fecha, 'fecha')}
      ELSE NULL
    END AS regla"""

    typed_select = ",\n  ".join(cols)
    raw_select = ",\n  ".join(f"raw_{column} AS {column}" for column in cols)
    qualify_parts = []
    for column in NATURAL_KEY[table]:
        ref = column
        if silver_type(table, column) == "DATE":
            ref = f"CAST({column} AS STRING)"
        qualify_parts.append(ref)
    qualify_key = ", ".join(qualify_parts)
    order_id = _order_id(table)

    cte = f"""WITH src AS (
  SELECT * FROM `{BRONZE_DATASET}.{table}`
),
typed AS (
  SELECT
{select_body}
  FROM src
),
flagged AS (
  SELECT
    *,
{motivo_case},
{regla_base}
  FROM typed
),
ranked AS (
  SELECT
    *,
    IF(
      motivo_base IS NULL,
      ROW_NUMBER() OVER (
        PARTITION BY
        {_partition_expr(table)}
        ORDER BY {order_id}
      ),
      NULL
    ) AS rn
  FROM flagged
),
resolved AS (
  SELECT
    ranked.*,
{motivo_resuelto},
{regla_resuelta}
  FROM ranked{join_sql}
)"""

    desc_silver = (
        f"Silver {table}. {NOTICE} Tipado con SAFE_CAST, una fila por llave natural, "
        f"FK contra silver. Expira a los {EXPIRATION_DAYS} días."
    )
    desc_q = (
        f"Cuarentena de {table}. {NOTICE} Una fila, un motivo, el de mayor prioridad. "
        f"Expira a los {EXPIRATION_DAYS} días."
    )
    header = f"""-- {SILVER_DATASET}.{table} y {SILVER_DATASET}.q_{table}
-- prioridad: {PRIORIDAD}
-- SAFE_CAST, TRIM, ROW_NUMBER. La FK mira la dimensión silver ya limpia.
-- BigQuery: EXTRACT(DAYOFWEEK) usa 1 = domingo, así que el lunes es 2.
-- {NOTICE}
"""
    silver = f"""CREATE OR REPLACE TABLE `{SILVER_DATASET}.{table}`
OPTIONS (
  description="{desc_silver}",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
{cte}
SELECT
  {typed_select}
FROM resolved
WHERE motivo IS NULL
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY {qualify_key}
  ORDER BY {order_id}
) = 1;
"""
    cuarentena = f"""CREATE OR REPLACE TABLE `{SILVER_DATASET}.q_{table}`
OPTIONS (
  description="{desc_q}",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
{cte}
SELECT
  {raw_select},
  motivo,
  regla
FROM resolved
WHERE motivo IS NOT NULL;
"""
    return header + "\n" + silver + "\n" + cuarentena


def render_all() -> dict[str, str]:
    return {table: render_sql(table) for table in TABLE_ORDER}


def motivos_en_orden() -> tuple[str, ...]:
    return MOTIVOS

-- csa_silver.partidas y csa_silver.q_partidas
-- prioridad: cast_fallido > nulo_obligatorio > duplicado > fk_huerfana > fecha_incoherente
-- SAFE_CAST, TRIM, ROW_NUMBER. La FK mira la dimensión silver ya limpia.
-- BigQuery: EXTRACT(DAYOFWEEK) usa 1 = domingo, así que el lunes es 2.
-- Lab de portafolio. Marca con fines ilustrativos.

CREATE OR REPLACE TABLE `csa_silver.partidas`
OPTIONS (
  description="Silver partidas. Lab de portafolio. Marca con fines ilustrativos. Tipado con SAFE_CAST, una fila por llave natural, FK contra silver. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
WITH src AS (
  SELECT * FROM `csa_bronze.partidas`
),
typed AS (
  SELECT
    src.partida_id AS raw_partida_id,
    src.obra_id AS raw_obra_id,
    src.codigo_partida AS raw_codigo_partida,
    src.partida_nombre AS raw_partida_nombre,
    src.capitulo AS raw_capitulo,
    src.unidad_medida AS raw_unidad_medida,
    src.cantidad_contrato AS raw_cantidad_contrato,
    src.precio_unitario AS raw_precio_unitario,
    src.hh_teorica_por_unidad AS raw_hh_teorica_por_unidad,
    NULLIF(UPPER(TRIM(CAST(src.partida_id AS STRING))), '') AS partida_id,
    NULLIF(UPPER(TRIM(CAST(src.obra_id AS STRING))), '') AS obra_id,
    NULLIF(TRIM(CAST(src.codigo_partida AS STRING)), '') AS codigo_partida,
    NULLIF(TRIM(CAST(src.partida_nombre AS STRING)), '') AS partida_nombre,
    NULLIF(LOWER(TRIM(CAST(src.capitulo AS STRING))), '') AS capitulo,
    NULLIF(LOWER(TRIM(CAST(src.unidad_medida AS STRING))), '') AS unidad_medida,
    SAFE_CAST(NULLIF(TRIM(CAST(src.cantidad_contrato AS STRING)), '') AS NUMERIC) AS cantidad_contrato,
    SAFE_CAST(NULLIF(TRIM(CAST(src.precio_unitario AS STRING)), '') AS NUMERIC) AS precio_unitario,
    SAFE_CAST(NULLIF(TRIM(CAST(src.hh_teorica_por_unidad AS STRING)), '') AS NUMERIC) AS hh_teorica_por_unidad,
    (NULLIF(TRIM(CAST(src.capitulo AS STRING)), '') IS NOT NULL AND LOWER(TRIM(CAST(src.capitulo AS STRING))) NOT IN ('drenaje', 'movimiento_tierras', 'obras_arte', 'pavimentos', 'senalizacion')) AS fail_capitulo,
    (NULLIF(TRIM(CAST(src.unidad_medida AS STRING)), '') IS NOT NULL AND LOWER(TRIM(CAST(src.unidad_medida AS STRING))) NOT IN ('kg', 'l', 'm2', 'm3', 'ml', 'ton', 'un')) AS fail_unidad_medida,
    (NULLIF(TRIM(CAST(src.cantidad_contrato AS STRING)), '') IS NOT NULL AND SAFE_CAST(NULLIF(TRIM(CAST(src.cantidad_contrato AS STRING)), '') AS NUMERIC) IS NULL) AS fail_cantidad_contrato,
    (NULLIF(TRIM(CAST(src.precio_unitario AS STRING)), '') IS NOT NULL AND SAFE_CAST(NULLIF(TRIM(CAST(src.precio_unitario AS STRING)), '') AS NUMERIC) IS NULL) AS fail_precio_unitario,
    (NULLIF(TRIM(CAST(src.hh_teorica_por_unidad AS STRING)), '') IS NOT NULL AND SAFE_CAST(NULLIF(TRIM(CAST(src.hh_teorica_por_unidad AS STRING)), '') AS NUMERIC) IS NULL) AS fail_hh_teorica_por_unidad
  FROM src
),
flagged AS (
  SELECT
    *,
    CASE
      WHEN fail_capitulo OR fail_unidad_medida OR fail_cantidad_contrato OR fail_precio_unitario OR fail_hh_teorica_por_unidad THEN 'cast_fallido'
      WHEN partida_id IS NULL OR obra_id IS NULL OR codigo_partida IS NULL OR partida_nombre IS NULL OR capitulo IS NULL OR unidad_medida IS NULL OR cantidad_contrato IS NULL OR precio_unitario IS NULL THEN 'nulo_obligatorio'
      ELSE NULL
    END AS motivo_base,
    CASE
      WHEN fail_capitulo THEN 'capitulo'
      WHEN fail_unidad_medida THEN 'unidad_medida'
      WHEN fail_cantidad_contrato THEN 'cantidad_contrato'
      WHEN fail_precio_unitario THEN 'precio_unitario'
      WHEN fail_hh_teorica_por_unidad THEN 'hh_teorica_por_unidad'
      WHEN partida_id IS NULL THEN 'partida_id'
      WHEN obra_id IS NULL THEN 'obra_id'
      WHEN codigo_partida IS NULL THEN 'codigo_partida'
      WHEN partida_nombre IS NULL THEN 'partida_nombre'
      WHEN capitulo IS NULL THEN 'capitulo'
      WHEN unidad_medida IS NULL THEN 'unidad_medida'
      WHEN cantidad_contrato IS NULL THEN 'cantidad_contrato'
      WHEN precio_unitario IS NULL THEN 'precio_unitario'
      ELSE NULL
    END AS regla_base
  FROM typed
),
ranked AS (
  SELECT
    *,
    IF(
      motivo_base IS NULL,
      ROW_NUMBER() OVER (
        PARTITION BY
        IF(motivo_base IS NULL, partida_id, NULL)
        ORDER BY partida_id
      ),
      NULL
    ) AS rn
  FROM flagged
),
resolved AS (
  SELECT
    ranked.*,
    CASE
      WHEN ranked.motivo_base IS NOT NULL THEN ranked.motivo_base
      WHEN ranked.rn > 1 THEN 'duplicado'
      WHEN dim_obras.obra_id IS NULL THEN 'fk_huerfana'
      WHEN FALSE THEN 'fecha_incoherente'
      ELSE NULL
    END AS motivo,
    CASE
      WHEN ranked.motivo_base IS NOT NULL THEN ranked.regla_base
      WHEN ranked.rn > 1 THEN 'llave natural'
      WHEN dim_obras.obra_id IS NULL THEN 'obra_id'
      WHEN FALSE THEN 'fecha'
      ELSE NULL
    END AS regla
  FROM ranked
  LEFT JOIN `csa_silver.obras` AS dim_obras
      ON ranked.obra_id = dim_obras.obra_id
)
SELECT
  partida_id,
  obra_id,
  codigo_partida,
  partida_nombre,
  capitulo,
  unidad_medida,
  cantidad_contrato,
  precio_unitario,
  hh_teorica_por_unidad
FROM resolved
WHERE motivo IS NULL
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY partida_id
  ORDER BY partida_id
) = 1;

CREATE OR REPLACE TABLE `csa_silver.q_partidas`
OPTIONS (
  description="Cuarentena de partidas. Lab de portafolio. Marca con fines ilustrativos. Una fila, un motivo, el de mayor prioridad. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
WITH src AS (
  SELECT * FROM `csa_bronze.partidas`
),
typed AS (
  SELECT
    src.partida_id AS raw_partida_id,
    src.obra_id AS raw_obra_id,
    src.codigo_partida AS raw_codigo_partida,
    src.partida_nombre AS raw_partida_nombre,
    src.capitulo AS raw_capitulo,
    src.unidad_medida AS raw_unidad_medida,
    src.cantidad_contrato AS raw_cantidad_contrato,
    src.precio_unitario AS raw_precio_unitario,
    src.hh_teorica_por_unidad AS raw_hh_teorica_por_unidad,
    NULLIF(UPPER(TRIM(CAST(src.partida_id AS STRING))), '') AS partida_id,
    NULLIF(UPPER(TRIM(CAST(src.obra_id AS STRING))), '') AS obra_id,
    NULLIF(TRIM(CAST(src.codigo_partida AS STRING)), '') AS codigo_partida,
    NULLIF(TRIM(CAST(src.partida_nombre AS STRING)), '') AS partida_nombre,
    NULLIF(LOWER(TRIM(CAST(src.capitulo AS STRING))), '') AS capitulo,
    NULLIF(LOWER(TRIM(CAST(src.unidad_medida AS STRING))), '') AS unidad_medida,
    SAFE_CAST(NULLIF(TRIM(CAST(src.cantidad_contrato AS STRING)), '') AS NUMERIC) AS cantidad_contrato,
    SAFE_CAST(NULLIF(TRIM(CAST(src.precio_unitario AS STRING)), '') AS NUMERIC) AS precio_unitario,
    SAFE_CAST(NULLIF(TRIM(CAST(src.hh_teorica_por_unidad AS STRING)), '') AS NUMERIC) AS hh_teorica_por_unidad,
    (NULLIF(TRIM(CAST(src.capitulo AS STRING)), '') IS NOT NULL AND LOWER(TRIM(CAST(src.capitulo AS STRING))) NOT IN ('drenaje', 'movimiento_tierras', 'obras_arte', 'pavimentos', 'senalizacion')) AS fail_capitulo,
    (NULLIF(TRIM(CAST(src.unidad_medida AS STRING)), '') IS NOT NULL AND LOWER(TRIM(CAST(src.unidad_medida AS STRING))) NOT IN ('kg', 'l', 'm2', 'm3', 'ml', 'ton', 'un')) AS fail_unidad_medida,
    (NULLIF(TRIM(CAST(src.cantidad_contrato AS STRING)), '') IS NOT NULL AND SAFE_CAST(NULLIF(TRIM(CAST(src.cantidad_contrato AS STRING)), '') AS NUMERIC) IS NULL) AS fail_cantidad_contrato,
    (NULLIF(TRIM(CAST(src.precio_unitario AS STRING)), '') IS NOT NULL AND SAFE_CAST(NULLIF(TRIM(CAST(src.precio_unitario AS STRING)), '') AS NUMERIC) IS NULL) AS fail_precio_unitario,
    (NULLIF(TRIM(CAST(src.hh_teorica_por_unidad AS STRING)), '') IS NOT NULL AND SAFE_CAST(NULLIF(TRIM(CAST(src.hh_teorica_por_unidad AS STRING)), '') AS NUMERIC) IS NULL) AS fail_hh_teorica_por_unidad
  FROM src
),
flagged AS (
  SELECT
    *,
    CASE
      WHEN fail_capitulo OR fail_unidad_medida OR fail_cantidad_contrato OR fail_precio_unitario OR fail_hh_teorica_por_unidad THEN 'cast_fallido'
      WHEN partida_id IS NULL OR obra_id IS NULL OR codigo_partida IS NULL OR partida_nombre IS NULL OR capitulo IS NULL OR unidad_medida IS NULL OR cantidad_contrato IS NULL OR precio_unitario IS NULL THEN 'nulo_obligatorio'
      ELSE NULL
    END AS motivo_base,
    CASE
      WHEN fail_capitulo THEN 'capitulo'
      WHEN fail_unidad_medida THEN 'unidad_medida'
      WHEN fail_cantidad_contrato THEN 'cantidad_contrato'
      WHEN fail_precio_unitario THEN 'precio_unitario'
      WHEN fail_hh_teorica_por_unidad THEN 'hh_teorica_por_unidad'
      WHEN partida_id IS NULL THEN 'partida_id'
      WHEN obra_id IS NULL THEN 'obra_id'
      WHEN codigo_partida IS NULL THEN 'codigo_partida'
      WHEN partida_nombre IS NULL THEN 'partida_nombre'
      WHEN capitulo IS NULL THEN 'capitulo'
      WHEN unidad_medida IS NULL THEN 'unidad_medida'
      WHEN cantidad_contrato IS NULL THEN 'cantidad_contrato'
      WHEN precio_unitario IS NULL THEN 'precio_unitario'
      ELSE NULL
    END AS regla_base
  FROM typed
),
ranked AS (
  SELECT
    *,
    IF(
      motivo_base IS NULL,
      ROW_NUMBER() OVER (
        PARTITION BY
        IF(motivo_base IS NULL, partida_id, NULL)
        ORDER BY partida_id
      ),
      NULL
    ) AS rn
  FROM flagged
),
resolved AS (
  SELECT
    ranked.*,
    CASE
      WHEN ranked.motivo_base IS NOT NULL THEN ranked.motivo_base
      WHEN ranked.rn > 1 THEN 'duplicado'
      WHEN dim_obras.obra_id IS NULL THEN 'fk_huerfana'
      WHEN FALSE THEN 'fecha_incoherente'
      ELSE NULL
    END AS motivo,
    CASE
      WHEN ranked.motivo_base IS NOT NULL THEN ranked.regla_base
      WHEN ranked.rn > 1 THEN 'llave natural'
      WHEN dim_obras.obra_id IS NULL THEN 'obra_id'
      WHEN FALSE THEN 'fecha'
      ELSE NULL
    END AS regla
  FROM ranked
  LEFT JOIN `csa_silver.obras` AS dim_obras
      ON ranked.obra_id = dim_obras.obra_id
)
SELECT
  raw_partida_id AS partida_id,
  raw_obra_id AS obra_id,
  raw_codigo_partida AS codigo_partida,
  raw_partida_nombre AS partida_nombre,
  raw_capitulo AS capitulo,
  raw_unidad_medida AS unidad_medida,
  raw_cantidad_contrato AS cantidad_contrato,
  raw_precio_unitario AS precio_unitario,
  raw_hh_teorica_por_unidad AS hh_teorica_por_unidad,
  motivo,
  regla
FROM resolved
WHERE motivo IS NOT NULL;

-- csa_silver.parte_hh y csa_silver.q_parte_hh
-- prioridad: cast_fallido > nulo_obligatorio > duplicado > fk_huerfana > fecha_incoherente
-- SAFE_CAST, TRIM, ROW_NUMBER. La FK mira la dimensión silver ya limpia.
-- BigQuery: EXTRACT(DAYOFWEEK) usa 1 = domingo, así que el lunes es 2.
-- Lab de portafolio. Marca con fines ilustrativos.

CREATE OR REPLACE TABLE `csa_silver.parte_hh`
OPTIONS (
  description="Silver parte_hh. Lab de portafolio. Marca con fines ilustrativos. Tipado con SAFE_CAST, una fila por llave natural, FK contra silver. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
WITH src AS (
  SELECT * FROM `csa_bronze.parte_hh`
),
typed AS (
  SELECT
    src.parte_id AS raw_parte_id,
    src.obra_id AS raw_obra_id,
    src.cuadrilla_id AS raw_cuadrilla_id,
    src.partida_id AS raw_partida_id,
    src.fecha AS raw_fecha,
    src.hh AS raw_hh,
    src.cantidad_ejecutada AS raw_cantidad_ejecutada,
    NULLIF(UPPER(TRIM(CAST(src.parte_id AS STRING))), '') AS parte_id,
    NULLIF(UPPER(TRIM(CAST(src.obra_id AS STRING))), '') AS obra_id,
    NULLIF(UPPER(TRIM(CAST(src.cuadrilla_id AS STRING))), '') AS cuadrilla_id,
    NULLIF(UPPER(TRIM(CAST(src.partida_id AS STRING))), '') AS partida_id,
    SAFE_CAST(NULLIF(TRIM(CAST(src.fecha AS STRING)), '') AS DATE) AS fecha,
    SAFE_CAST(NULLIF(TRIM(CAST(src.hh AS STRING)), '') AS NUMERIC) AS hh,
    SAFE_CAST(NULLIF(TRIM(CAST(src.cantidad_ejecutada AS STRING)), '') AS NUMERIC) AS cantidad_ejecutada,
    (NULLIF(TRIM(CAST(src.fecha AS STRING)), '') IS NOT NULL AND SAFE_CAST(NULLIF(TRIM(CAST(src.fecha AS STRING)), '') AS DATE) IS NULL) AS fail_fecha,
    (NULLIF(TRIM(CAST(src.hh AS STRING)), '') IS NOT NULL AND SAFE_CAST(NULLIF(TRIM(CAST(src.hh AS STRING)), '') AS NUMERIC) IS NULL) AS fail_hh,
    (NULLIF(TRIM(CAST(src.cantidad_ejecutada AS STRING)), '') IS NOT NULL AND SAFE_CAST(NULLIF(TRIM(CAST(src.cantidad_ejecutada AS STRING)), '') AS NUMERIC) IS NULL) AS fail_cantidad_ejecutada
  FROM src
),
flagged AS (
  SELECT
    *,
    CASE
      WHEN fail_fecha OR fail_hh OR fail_cantidad_ejecutada THEN 'cast_fallido'
      WHEN parte_id IS NULL OR obra_id IS NULL OR cuadrilla_id IS NULL OR partida_id IS NULL OR fecha IS NULL OR hh IS NULL OR cantidad_ejecutada IS NULL THEN 'nulo_obligatorio'
      ELSE NULL
    END AS motivo_base,
    CASE
      WHEN fail_fecha THEN 'fecha'
      WHEN fail_hh THEN 'hh'
      WHEN fail_cantidad_ejecutada THEN 'cantidad_ejecutada'
      WHEN parte_id IS NULL THEN 'parte_id'
      WHEN obra_id IS NULL THEN 'obra_id'
      WHEN cuadrilla_id IS NULL THEN 'cuadrilla_id'
      WHEN partida_id IS NULL THEN 'partida_id'
      WHEN fecha IS NULL THEN 'fecha'
      WHEN hh IS NULL THEN 'hh'
      WHEN cantidad_ejecutada IS NULL THEN 'cantidad_ejecutada'
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
        IF(motivo_base IS NULL, obra_id, NULL),
        IF(motivo_base IS NULL, cuadrilla_id, NULL),
        IF(motivo_base IS NULL, CAST(fecha AS STRING), NULL)
        ORDER BY parte_id
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
      WHEN (dim_obras.obra_id IS NULL) OR (dim_cuadrillas.cuadrilla_id IS NULL) OR (dim_cuadrillas.obra_id != ranked.obra_id) OR (dim_partidas.partida_id IS NULL) OR (dim_partidas.obra_id != ranked.obra_id) THEN 'fk_huerfana'
      WHEN (ranked.fecha < dim_obras.fecha_inicio) OR (ranked.fecha > dim_obras.fecha_termino) THEN 'fecha_incoherente'
      ELSE NULL
    END AS motivo,
    CASE
      WHEN ranked.motivo_base IS NOT NULL THEN ranked.regla_base
      WHEN ranked.rn > 1 THEN 'llave natural'
      WHEN dim_obras.obra_id IS NULL THEN 'obra_id'
      WHEN dim_cuadrillas.cuadrilla_id IS NULL THEN 'cuadrilla_id'
      WHEN dim_cuadrillas.obra_id != ranked.obra_id THEN 'cuadrilla_id'
      WHEN dim_partidas.partida_id IS NULL THEN 'partida_id'
      WHEN dim_partidas.obra_id != ranked.obra_id THEN 'partida_id'
      WHEN ranked.fecha < dim_obras.fecha_inicio THEN 'fecha'
      WHEN ranked.fecha > dim_obras.fecha_termino THEN 'fecha'
      ELSE NULL
    END AS regla
  FROM ranked
  LEFT JOIN `csa_silver.obras` AS dim_obras
      ON ranked.obra_id = dim_obras.obra_id
  LEFT JOIN `csa_silver.cuadrillas` AS dim_cuadrillas
      ON ranked.cuadrilla_id = dim_cuadrillas.cuadrilla_id
  LEFT JOIN `csa_silver.partidas` AS dim_partidas
      ON ranked.partida_id = dim_partidas.partida_id
)
SELECT
  parte_id,
  obra_id,
  cuadrilla_id,
  partida_id,
  fecha,
  hh,
  cantidad_ejecutada
FROM resolved
WHERE motivo IS NULL
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY obra_id, cuadrilla_id, CAST(fecha AS STRING)
  ORDER BY parte_id
) = 1;

CREATE OR REPLACE TABLE `csa_silver.q_parte_hh`
OPTIONS (
  description="Cuarentena de parte_hh. Lab de portafolio. Marca con fines ilustrativos. Una fila, un motivo, el de mayor prioridad. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
WITH src AS (
  SELECT * FROM `csa_bronze.parte_hh`
),
typed AS (
  SELECT
    src.parte_id AS raw_parte_id,
    src.obra_id AS raw_obra_id,
    src.cuadrilla_id AS raw_cuadrilla_id,
    src.partida_id AS raw_partida_id,
    src.fecha AS raw_fecha,
    src.hh AS raw_hh,
    src.cantidad_ejecutada AS raw_cantidad_ejecutada,
    NULLIF(UPPER(TRIM(CAST(src.parte_id AS STRING))), '') AS parte_id,
    NULLIF(UPPER(TRIM(CAST(src.obra_id AS STRING))), '') AS obra_id,
    NULLIF(UPPER(TRIM(CAST(src.cuadrilla_id AS STRING))), '') AS cuadrilla_id,
    NULLIF(UPPER(TRIM(CAST(src.partida_id AS STRING))), '') AS partida_id,
    SAFE_CAST(NULLIF(TRIM(CAST(src.fecha AS STRING)), '') AS DATE) AS fecha,
    SAFE_CAST(NULLIF(TRIM(CAST(src.hh AS STRING)), '') AS NUMERIC) AS hh,
    SAFE_CAST(NULLIF(TRIM(CAST(src.cantidad_ejecutada AS STRING)), '') AS NUMERIC) AS cantidad_ejecutada,
    (NULLIF(TRIM(CAST(src.fecha AS STRING)), '') IS NOT NULL AND SAFE_CAST(NULLIF(TRIM(CAST(src.fecha AS STRING)), '') AS DATE) IS NULL) AS fail_fecha,
    (NULLIF(TRIM(CAST(src.hh AS STRING)), '') IS NOT NULL AND SAFE_CAST(NULLIF(TRIM(CAST(src.hh AS STRING)), '') AS NUMERIC) IS NULL) AS fail_hh,
    (NULLIF(TRIM(CAST(src.cantidad_ejecutada AS STRING)), '') IS NOT NULL AND SAFE_CAST(NULLIF(TRIM(CAST(src.cantidad_ejecutada AS STRING)), '') AS NUMERIC) IS NULL) AS fail_cantidad_ejecutada
  FROM src
),
flagged AS (
  SELECT
    *,
    CASE
      WHEN fail_fecha OR fail_hh OR fail_cantidad_ejecutada THEN 'cast_fallido'
      WHEN parte_id IS NULL OR obra_id IS NULL OR cuadrilla_id IS NULL OR partida_id IS NULL OR fecha IS NULL OR hh IS NULL OR cantidad_ejecutada IS NULL THEN 'nulo_obligatorio'
      ELSE NULL
    END AS motivo_base,
    CASE
      WHEN fail_fecha THEN 'fecha'
      WHEN fail_hh THEN 'hh'
      WHEN fail_cantidad_ejecutada THEN 'cantidad_ejecutada'
      WHEN parte_id IS NULL THEN 'parte_id'
      WHEN obra_id IS NULL THEN 'obra_id'
      WHEN cuadrilla_id IS NULL THEN 'cuadrilla_id'
      WHEN partida_id IS NULL THEN 'partida_id'
      WHEN fecha IS NULL THEN 'fecha'
      WHEN hh IS NULL THEN 'hh'
      WHEN cantidad_ejecutada IS NULL THEN 'cantidad_ejecutada'
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
        IF(motivo_base IS NULL, obra_id, NULL),
        IF(motivo_base IS NULL, cuadrilla_id, NULL),
        IF(motivo_base IS NULL, CAST(fecha AS STRING), NULL)
        ORDER BY parte_id
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
      WHEN (dim_obras.obra_id IS NULL) OR (dim_cuadrillas.cuadrilla_id IS NULL) OR (dim_cuadrillas.obra_id != ranked.obra_id) OR (dim_partidas.partida_id IS NULL) OR (dim_partidas.obra_id != ranked.obra_id) THEN 'fk_huerfana'
      WHEN (ranked.fecha < dim_obras.fecha_inicio) OR (ranked.fecha > dim_obras.fecha_termino) THEN 'fecha_incoherente'
      ELSE NULL
    END AS motivo,
    CASE
      WHEN ranked.motivo_base IS NOT NULL THEN ranked.regla_base
      WHEN ranked.rn > 1 THEN 'llave natural'
      WHEN dim_obras.obra_id IS NULL THEN 'obra_id'
      WHEN dim_cuadrillas.cuadrilla_id IS NULL THEN 'cuadrilla_id'
      WHEN dim_cuadrillas.obra_id != ranked.obra_id THEN 'cuadrilla_id'
      WHEN dim_partidas.partida_id IS NULL THEN 'partida_id'
      WHEN dim_partidas.obra_id != ranked.obra_id THEN 'partida_id'
      WHEN ranked.fecha < dim_obras.fecha_inicio THEN 'fecha'
      WHEN ranked.fecha > dim_obras.fecha_termino THEN 'fecha'
      ELSE NULL
    END AS regla
  FROM ranked
  LEFT JOIN `csa_silver.obras` AS dim_obras
      ON ranked.obra_id = dim_obras.obra_id
  LEFT JOIN `csa_silver.cuadrillas` AS dim_cuadrillas
      ON ranked.cuadrilla_id = dim_cuadrillas.cuadrilla_id
  LEFT JOIN `csa_silver.partidas` AS dim_partidas
      ON ranked.partida_id = dim_partidas.partida_id
)
SELECT
  raw_parte_id AS parte_id,
  raw_obra_id AS obra_id,
  raw_cuadrilla_id AS cuadrilla_id,
  raw_partida_id AS partida_id,
  raw_fecha AS fecha,
  raw_hh AS hh,
  raw_cantidad_ejecutada AS cantidad_ejecutada,
  motivo,
  regla
FROM resolved
WHERE motivo IS NOT NULL;

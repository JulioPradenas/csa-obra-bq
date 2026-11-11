-- csa_silver.programa_avance y csa_silver.q_programa_avance
-- prioridad: cast_fallido > nulo_obligatorio > duplicado > fk_huerfana > fecha_incoherente
-- SAFE_CAST, TRIM, ROW_NUMBER. La FK mira la dimensión silver ya limpia.
-- BigQuery: EXTRACT(DAYOFWEEK) usa 1 = domingo, así que el lunes es 2.
-- Lab de portafolio. Marca con fines ilustrativos.

CREATE OR REPLACE TABLE `csa_silver.programa_avance`
OPTIONS (
  description="Silver programa_avance. Lab de portafolio. Marca con fines ilustrativos. Tipado con SAFE_CAST, una fila por llave natural, FK contra silver. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
WITH src AS (
  SELECT * FROM `csa_bronze.programa_avance`
),
typed AS (
  SELECT
    src.programa_id AS raw_programa_id,
    src.obra_id AS raw_obra_id,
    src.partida_id AS raw_partida_id,
    src.semana_lunes AS raw_semana_lunes,
    src.cantidad_programada AS raw_cantidad_programada,
    NULLIF(UPPER(TRIM(CAST(src.programa_id AS STRING))), '') AS programa_id,
    NULLIF(UPPER(TRIM(CAST(src.obra_id AS STRING))), '') AS obra_id,
    NULLIF(UPPER(TRIM(CAST(src.partida_id AS STRING))), '') AS partida_id,
    SAFE_CAST(NULLIF(TRIM(CAST(src.semana_lunes AS STRING)), '') AS DATE) AS semana_lunes,
    SAFE_CAST(NULLIF(TRIM(CAST(src.cantidad_programada AS STRING)), '') AS NUMERIC) AS cantidad_programada,
    (NULLIF(TRIM(CAST(src.semana_lunes AS STRING)), '') IS NOT NULL AND SAFE_CAST(NULLIF(TRIM(CAST(src.semana_lunes AS STRING)), '') AS DATE) IS NULL) AS fail_semana_lunes,
    (NULLIF(TRIM(CAST(src.cantidad_programada AS STRING)), '') IS NOT NULL AND SAFE_CAST(NULLIF(TRIM(CAST(src.cantidad_programada AS STRING)), '') AS NUMERIC) IS NULL) AS fail_cantidad_programada
  FROM src
),
flagged AS (
  SELECT
    *,
    CASE
      WHEN fail_semana_lunes OR fail_cantidad_programada THEN 'cast_fallido'
      WHEN programa_id IS NULL OR obra_id IS NULL OR partida_id IS NULL OR semana_lunes IS NULL OR cantidad_programada IS NULL THEN 'nulo_obligatorio'
      ELSE NULL
    END AS motivo_base,
    CASE
      WHEN fail_semana_lunes THEN 'semana_lunes'
      WHEN fail_cantidad_programada THEN 'cantidad_programada'
      WHEN programa_id IS NULL THEN 'programa_id'
      WHEN obra_id IS NULL THEN 'obra_id'
      WHEN partida_id IS NULL THEN 'partida_id'
      WHEN semana_lunes IS NULL THEN 'semana_lunes'
      WHEN cantidad_programada IS NULL THEN 'cantidad_programada'
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
        IF(motivo_base IS NULL, partida_id, NULL),
        IF(motivo_base IS NULL, CAST(semana_lunes AS STRING), NULL)
        ORDER BY programa_id
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
      WHEN (dim_obras.obra_id IS NULL) OR (dim_partidas.partida_id IS NULL) OR (dim_partidas.obra_id != ranked.obra_id) THEN 'fk_huerfana'
      WHEN (EXTRACT(DAYOFWEEK FROM ranked.semana_lunes) != 2) OR (ranked.semana_lunes < dim_obras.fecha_inicio) OR (ranked.semana_lunes > dim_obras.fecha_termino) THEN 'fecha_incoherente'
      ELSE NULL
    END AS motivo,
    CASE
      WHEN ranked.motivo_base IS NOT NULL THEN ranked.regla_base
      WHEN ranked.rn > 1 THEN 'llave natural'
      WHEN dim_obras.obra_id IS NULL THEN 'obra_id'
      WHEN dim_partidas.partida_id IS NULL THEN 'partida_id'
      WHEN dim_partidas.obra_id != ranked.obra_id THEN 'partida_id'
      WHEN EXTRACT(DAYOFWEEK FROM ranked.semana_lunes) != 2 THEN 'semana_lunes'
      WHEN ranked.semana_lunes < dim_obras.fecha_inicio THEN 'semana_lunes'
      WHEN ranked.semana_lunes > dim_obras.fecha_termino THEN 'semana_lunes'
      ELSE NULL
    END AS regla
  FROM ranked
  LEFT JOIN `csa_silver.obras` AS dim_obras
      ON ranked.obra_id = dim_obras.obra_id
  LEFT JOIN `csa_silver.partidas` AS dim_partidas
      ON ranked.partida_id = dim_partidas.partida_id
)
SELECT
  programa_id,
  obra_id,
  partida_id,
  semana_lunes,
  cantidad_programada
FROM resolved
WHERE motivo IS NULL
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY obra_id, partida_id, CAST(semana_lunes AS STRING)
  ORDER BY programa_id
) = 1;

CREATE OR REPLACE TABLE `csa_silver.q_programa_avance`
OPTIONS (
  description="Cuarentena de programa_avance. Lab de portafolio. Marca con fines ilustrativos. Una fila, un motivo, el de mayor prioridad. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
WITH src AS (
  SELECT * FROM `csa_bronze.programa_avance`
),
typed AS (
  SELECT
    src.programa_id AS raw_programa_id,
    src.obra_id AS raw_obra_id,
    src.partida_id AS raw_partida_id,
    src.semana_lunes AS raw_semana_lunes,
    src.cantidad_programada AS raw_cantidad_programada,
    NULLIF(UPPER(TRIM(CAST(src.programa_id AS STRING))), '') AS programa_id,
    NULLIF(UPPER(TRIM(CAST(src.obra_id AS STRING))), '') AS obra_id,
    NULLIF(UPPER(TRIM(CAST(src.partida_id AS STRING))), '') AS partida_id,
    SAFE_CAST(NULLIF(TRIM(CAST(src.semana_lunes AS STRING)), '') AS DATE) AS semana_lunes,
    SAFE_CAST(NULLIF(TRIM(CAST(src.cantidad_programada AS STRING)), '') AS NUMERIC) AS cantidad_programada,
    (NULLIF(TRIM(CAST(src.semana_lunes AS STRING)), '') IS NOT NULL AND SAFE_CAST(NULLIF(TRIM(CAST(src.semana_lunes AS STRING)), '') AS DATE) IS NULL) AS fail_semana_lunes,
    (NULLIF(TRIM(CAST(src.cantidad_programada AS STRING)), '') IS NOT NULL AND SAFE_CAST(NULLIF(TRIM(CAST(src.cantidad_programada AS STRING)), '') AS NUMERIC) IS NULL) AS fail_cantidad_programada
  FROM src
),
flagged AS (
  SELECT
    *,
    CASE
      WHEN fail_semana_lunes OR fail_cantidad_programada THEN 'cast_fallido'
      WHEN programa_id IS NULL OR obra_id IS NULL OR partida_id IS NULL OR semana_lunes IS NULL OR cantidad_programada IS NULL THEN 'nulo_obligatorio'
      ELSE NULL
    END AS motivo_base,
    CASE
      WHEN fail_semana_lunes THEN 'semana_lunes'
      WHEN fail_cantidad_programada THEN 'cantidad_programada'
      WHEN programa_id IS NULL THEN 'programa_id'
      WHEN obra_id IS NULL THEN 'obra_id'
      WHEN partida_id IS NULL THEN 'partida_id'
      WHEN semana_lunes IS NULL THEN 'semana_lunes'
      WHEN cantidad_programada IS NULL THEN 'cantidad_programada'
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
        IF(motivo_base IS NULL, partida_id, NULL),
        IF(motivo_base IS NULL, CAST(semana_lunes AS STRING), NULL)
        ORDER BY programa_id
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
      WHEN (dim_obras.obra_id IS NULL) OR (dim_partidas.partida_id IS NULL) OR (dim_partidas.obra_id != ranked.obra_id) THEN 'fk_huerfana'
      WHEN (EXTRACT(DAYOFWEEK FROM ranked.semana_lunes) != 2) OR (ranked.semana_lunes < dim_obras.fecha_inicio) OR (ranked.semana_lunes > dim_obras.fecha_termino) THEN 'fecha_incoherente'
      ELSE NULL
    END AS motivo,
    CASE
      WHEN ranked.motivo_base IS NOT NULL THEN ranked.regla_base
      WHEN ranked.rn > 1 THEN 'llave natural'
      WHEN dim_obras.obra_id IS NULL THEN 'obra_id'
      WHEN dim_partidas.partida_id IS NULL THEN 'partida_id'
      WHEN dim_partidas.obra_id != ranked.obra_id THEN 'partida_id'
      WHEN EXTRACT(DAYOFWEEK FROM ranked.semana_lunes) != 2 THEN 'semana_lunes'
      WHEN ranked.semana_lunes < dim_obras.fecha_inicio THEN 'semana_lunes'
      WHEN ranked.semana_lunes > dim_obras.fecha_termino THEN 'semana_lunes'
      ELSE NULL
    END AS regla
  FROM ranked
  LEFT JOIN `csa_silver.obras` AS dim_obras
      ON ranked.obra_id = dim_obras.obra_id
  LEFT JOIN `csa_silver.partidas` AS dim_partidas
      ON ranked.partida_id = dim_partidas.partida_id
)
SELECT
  raw_programa_id AS programa_id,
  raw_obra_id AS obra_id,
  raw_partida_id AS partida_id,
  raw_semana_lunes AS semana_lunes,
  raw_cantidad_programada AS cantidad_programada,
  motivo,
  regla
FROM resolved
WHERE motivo IS NOT NULL;

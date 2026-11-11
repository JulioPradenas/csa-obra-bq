-- csa_silver.vale_consumo y csa_silver.q_vale_consumo
-- prioridad: cast_fallido > nulo_obligatorio > duplicado > fk_huerfana > fecha_incoherente
-- SAFE_CAST, TRIM, ROW_NUMBER. La FK mira la dimensión silver ya limpia.
-- BigQuery: EXTRACT(DAYOFWEEK) usa 1 = domingo, así que el lunes es 2.
-- Lab de portafolio. Marca con fines ilustrativos.

CREATE OR REPLACE TABLE `csa_silver.vale_consumo`
OPTIONS (
  description="Silver vale_consumo. Lab de portafolio. Marca con fines ilustrativos. Tipado con SAFE_CAST, una fila por llave natural, FK contra silver. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
WITH src AS (
  SELECT * FROM `csa_bronze.vale_consumo`
),
typed AS (
  SELECT
    src.vale_id AS raw_vale_id,
    src.obra_id AS raw_obra_id,
    src.material_id AS raw_material_id,
    src.semana_lunes AS raw_semana_lunes,
    src.cantidad_real AS raw_cantidad_real,
    NULLIF(UPPER(TRIM(CAST(src.vale_id AS STRING))), '') AS vale_id,
    NULLIF(UPPER(TRIM(CAST(src.obra_id AS STRING))), '') AS obra_id,
    NULLIF(UPPER(TRIM(CAST(src.material_id AS STRING))), '') AS material_id,
    SAFE_CAST(NULLIF(TRIM(CAST(src.semana_lunes AS STRING)), '') AS DATE) AS semana_lunes,
    SAFE_CAST(NULLIF(TRIM(CAST(src.cantidad_real AS STRING)), '') AS NUMERIC) AS cantidad_real,
    (NULLIF(TRIM(CAST(src.semana_lunes AS STRING)), '') IS NOT NULL AND SAFE_CAST(NULLIF(TRIM(CAST(src.semana_lunes AS STRING)), '') AS DATE) IS NULL) AS fail_semana_lunes,
    (NULLIF(TRIM(CAST(src.cantidad_real AS STRING)), '') IS NOT NULL AND SAFE_CAST(NULLIF(TRIM(CAST(src.cantidad_real AS STRING)), '') AS NUMERIC) IS NULL) AS fail_cantidad_real
  FROM src
),
flagged AS (
  SELECT
    *,
    CASE
      WHEN fail_semana_lunes OR fail_cantidad_real THEN 'cast_fallido'
      WHEN vale_id IS NULL OR obra_id IS NULL OR material_id IS NULL OR semana_lunes IS NULL OR cantidad_real IS NULL THEN 'nulo_obligatorio'
      ELSE NULL
    END AS motivo_base,
    CASE
      WHEN fail_semana_lunes THEN 'semana_lunes'
      WHEN fail_cantidad_real THEN 'cantidad_real'
      WHEN vale_id IS NULL THEN 'vale_id'
      WHEN obra_id IS NULL THEN 'obra_id'
      WHEN material_id IS NULL THEN 'material_id'
      WHEN semana_lunes IS NULL THEN 'semana_lunes'
      WHEN cantidad_real IS NULL THEN 'cantidad_real'
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
        IF(motivo_base IS NULL, material_id, NULL),
        IF(motivo_base IS NULL, CAST(semana_lunes AS STRING), NULL)
        ORDER BY vale_id
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
      WHEN (dim_obras.obra_id IS NULL) OR (dim_materiales.material_id IS NULL) THEN 'fk_huerfana'
      WHEN (EXTRACT(DAYOFWEEK FROM ranked.semana_lunes) != 2) OR (ranked.semana_lunes < dim_obras.fecha_inicio) OR (ranked.semana_lunes > dim_obras.fecha_termino) THEN 'fecha_incoherente'
      ELSE NULL
    END AS motivo,
    CASE
      WHEN ranked.motivo_base IS NOT NULL THEN ranked.regla_base
      WHEN ranked.rn > 1 THEN 'llave natural'
      WHEN dim_obras.obra_id IS NULL THEN 'obra_id'
      WHEN dim_materiales.material_id IS NULL THEN 'material_id'
      WHEN EXTRACT(DAYOFWEEK FROM ranked.semana_lunes) != 2 THEN 'semana_lunes'
      WHEN ranked.semana_lunes < dim_obras.fecha_inicio THEN 'semana_lunes'
      WHEN ranked.semana_lunes > dim_obras.fecha_termino THEN 'semana_lunes'
      ELSE NULL
    END AS regla
  FROM ranked
  LEFT JOIN `csa_silver.obras` AS dim_obras
      ON ranked.obra_id = dim_obras.obra_id
  LEFT JOIN `csa_silver.materiales` AS dim_materiales
      ON ranked.material_id = dim_materiales.material_id
)
SELECT
  vale_id,
  obra_id,
  material_id,
  semana_lunes,
  cantidad_real
FROM resolved
WHERE motivo IS NULL
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY obra_id, material_id, CAST(semana_lunes AS STRING)
  ORDER BY vale_id
) = 1;

CREATE OR REPLACE TABLE `csa_silver.q_vale_consumo`
OPTIONS (
  description="Cuarentena de vale_consumo. Lab de portafolio. Marca con fines ilustrativos. Una fila, un motivo, el de mayor prioridad. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
WITH src AS (
  SELECT * FROM `csa_bronze.vale_consumo`
),
typed AS (
  SELECT
    src.vale_id AS raw_vale_id,
    src.obra_id AS raw_obra_id,
    src.material_id AS raw_material_id,
    src.semana_lunes AS raw_semana_lunes,
    src.cantidad_real AS raw_cantidad_real,
    NULLIF(UPPER(TRIM(CAST(src.vale_id AS STRING))), '') AS vale_id,
    NULLIF(UPPER(TRIM(CAST(src.obra_id AS STRING))), '') AS obra_id,
    NULLIF(UPPER(TRIM(CAST(src.material_id AS STRING))), '') AS material_id,
    SAFE_CAST(NULLIF(TRIM(CAST(src.semana_lunes AS STRING)), '') AS DATE) AS semana_lunes,
    SAFE_CAST(NULLIF(TRIM(CAST(src.cantidad_real AS STRING)), '') AS NUMERIC) AS cantidad_real,
    (NULLIF(TRIM(CAST(src.semana_lunes AS STRING)), '') IS NOT NULL AND SAFE_CAST(NULLIF(TRIM(CAST(src.semana_lunes AS STRING)), '') AS DATE) IS NULL) AS fail_semana_lunes,
    (NULLIF(TRIM(CAST(src.cantidad_real AS STRING)), '') IS NOT NULL AND SAFE_CAST(NULLIF(TRIM(CAST(src.cantidad_real AS STRING)), '') AS NUMERIC) IS NULL) AS fail_cantidad_real
  FROM src
),
flagged AS (
  SELECT
    *,
    CASE
      WHEN fail_semana_lunes OR fail_cantidad_real THEN 'cast_fallido'
      WHEN vale_id IS NULL OR obra_id IS NULL OR material_id IS NULL OR semana_lunes IS NULL OR cantidad_real IS NULL THEN 'nulo_obligatorio'
      ELSE NULL
    END AS motivo_base,
    CASE
      WHEN fail_semana_lunes THEN 'semana_lunes'
      WHEN fail_cantidad_real THEN 'cantidad_real'
      WHEN vale_id IS NULL THEN 'vale_id'
      WHEN obra_id IS NULL THEN 'obra_id'
      WHEN material_id IS NULL THEN 'material_id'
      WHEN semana_lunes IS NULL THEN 'semana_lunes'
      WHEN cantidad_real IS NULL THEN 'cantidad_real'
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
        IF(motivo_base IS NULL, material_id, NULL),
        IF(motivo_base IS NULL, CAST(semana_lunes AS STRING), NULL)
        ORDER BY vale_id
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
      WHEN (dim_obras.obra_id IS NULL) OR (dim_materiales.material_id IS NULL) THEN 'fk_huerfana'
      WHEN (EXTRACT(DAYOFWEEK FROM ranked.semana_lunes) != 2) OR (ranked.semana_lunes < dim_obras.fecha_inicio) OR (ranked.semana_lunes > dim_obras.fecha_termino) THEN 'fecha_incoherente'
      ELSE NULL
    END AS motivo,
    CASE
      WHEN ranked.motivo_base IS NOT NULL THEN ranked.regla_base
      WHEN ranked.rn > 1 THEN 'llave natural'
      WHEN dim_obras.obra_id IS NULL THEN 'obra_id'
      WHEN dim_materiales.material_id IS NULL THEN 'material_id'
      WHEN EXTRACT(DAYOFWEEK FROM ranked.semana_lunes) != 2 THEN 'semana_lunes'
      WHEN ranked.semana_lunes < dim_obras.fecha_inicio THEN 'semana_lunes'
      WHEN ranked.semana_lunes > dim_obras.fecha_termino THEN 'semana_lunes'
      ELSE NULL
    END AS regla
  FROM ranked
  LEFT JOIN `csa_silver.obras` AS dim_obras
      ON ranked.obra_id = dim_obras.obra_id
  LEFT JOIN `csa_silver.materiales` AS dim_materiales
      ON ranked.material_id = dim_materiales.material_id
)
SELECT
  raw_vale_id AS vale_id,
  raw_obra_id AS obra_id,
  raw_material_id AS material_id,
  raw_semana_lunes AS semana_lunes,
  raw_cantidad_real AS cantidad_real,
  motivo,
  regla
FROM resolved
WHERE motivo IS NOT NULL;

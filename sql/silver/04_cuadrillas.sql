-- csa_silver.cuadrillas y csa_silver.q_cuadrillas
-- prioridad: cast_fallido > nulo_obligatorio > duplicado > fk_huerfana > fecha_incoherente
-- SAFE_CAST, TRIM, ROW_NUMBER. La FK mira la dimensión silver ya limpia.
-- BigQuery: EXTRACT(DAYOFWEEK) usa 1 = domingo, así que el lunes es 2.
-- Lab de portafolio. Marca con fines ilustrativos.

CREATE OR REPLACE TABLE `csa_silver.cuadrillas`
OPTIONS (
  description="Silver cuadrillas. Lab de portafolio. Marca con fines ilustrativos. Tipado con SAFE_CAST, una fila por llave natural, FK contra silver. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
WITH src AS (
  SELECT * FROM `csa_bronze.cuadrillas`
),
typed AS (
  SELECT
    src.cuadrilla_id AS raw_cuadrilla_id,
    src.cuadrilla_nombre AS raw_cuadrilla_nombre,
    src.especialidad AS raw_especialidad,
    src.obra_id AS raw_obra_id,
    src.activo AS raw_activo,
    NULLIF(UPPER(TRIM(CAST(src.cuadrilla_id AS STRING))), '') AS cuadrilla_id,
    NULLIF(TRIM(CAST(src.cuadrilla_nombre AS STRING)), '') AS cuadrilla_nombre,
    NULLIF(LOWER(TRIM(CAST(src.especialidad AS STRING))), '') AS especialidad,
    NULLIF(UPPER(TRIM(CAST(src.obra_id AS STRING))), '') AS obra_id,
    CASE
        WHEN NULLIF(TRIM(CAST(src.activo AS STRING)), '') IS NULL THEN NULL
        WHEN TRIM(CAST(src.activo AS STRING)) IN ('true', 'True', '1') THEN TRUE
        WHEN TRIM(CAST(src.activo AS STRING)) IN ('false', 'False', '0') THEN FALSE
        ELSE NULL
      END AS activo,
    (NULLIF(TRIM(CAST(src.especialidad AS STRING)), '') IS NOT NULL AND LOWER(TRIM(CAST(src.especialidad AS STRING))) NOT IN ('estructuras', 'pavimento', 'senalizacion', 'tierras')) AS fail_especialidad,
    (NULLIF(TRIM(CAST(src.activo AS STRING)), '') IS NOT NULL AND TRIM(CAST(src.activo AS STRING)) NOT IN ('0', '1', 'False', 'True', 'false', 'true')) AS fail_activo
  FROM src
),
flagged AS (
  SELECT
    *,
    CASE
      WHEN fail_especialidad OR fail_activo THEN 'cast_fallido'
      WHEN cuadrilla_id IS NULL OR cuadrilla_nombre IS NULL OR especialidad IS NULL OR obra_id IS NULL OR activo IS NULL THEN 'nulo_obligatorio'
      ELSE NULL
    END AS motivo_base,
    CASE
      WHEN fail_especialidad THEN 'especialidad'
      WHEN fail_activo THEN 'activo'
      WHEN cuadrilla_id IS NULL THEN 'cuadrilla_id'
      WHEN cuadrilla_nombre IS NULL THEN 'cuadrilla_nombre'
      WHEN especialidad IS NULL THEN 'especialidad'
      WHEN obra_id IS NULL THEN 'obra_id'
      WHEN activo IS NULL THEN 'activo'
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
        IF(motivo_base IS NULL, cuadrilla_id, NULL)
        ORDER BY cuadrilla_id
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
  cuadrilla_id,
  cuadrilla_nombre,
  especialidad,
  obra_id,
  activo
FROM resolved
WHERE motivo IS NULL
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY cuadrilla_id
  ORDER BY cuadrilla_id
) = 1;

CREATE OR REPLACE TABLE `csa_silver.q_cuadrillas`
OPTIONS (
  description="Cuarentena de cuadrillas. Lab de portafolio. Marca con fines ilustrativos. Una fila, un motivo, el de mayor prioridad. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
WITH src AS (
  SELECT * FROM `csa_bronze.cuadrillas`
),
typed AS (
  SELECT
    src.cuadrilla_id AS raw_cuadrilla_id,
    src.cuadrilla_nombre AS raw_cuadrilla_nombre,
    src.especialidad AS raw_especialidad,
    src.obra_id AS raw_obra_id,
    src.activo AS raw_activo,
    NULLIF(UPPER(TRIM(CAST(src.cuadrilla_id AS STRING))), '') AS cuadrilla_id,
    NULLIF(TRIM(CAST(src.cuadrilla_nombre AS STRING)), '') AS cuadrilla_nombre,
    NULLIF(LOWER(TRIM(CAST(src.especialidad AS STRING))), '') AS especialidad,
    NULLIF(UPPER(TRIM(CAST(src.obra_id AS STRING))), '') AS obra_id,
    CASE
        WHEN NULLIF(TRIM(CAST(src.activo AS STRING)), '') IS NULL THEN NULL
        WHEN TRIM(CAST(src.activo AS STRING)) IN ('true', 'True', '1') THEN TRUE
        WHEN TRIM(CAST(src.activo AS STRING)) IN ('false', 'False', '0') THEN FALSE
        ELSE NULL
      END AS activo,
    (NULLIF(TRIM(CAST(src.especialidad AS STRING)), '') IS NOT NULL AND LOWER(TRIM(CAST(src.especialidad AS STRING))) NOT IN ('estructuras', 'pavimento', 'senalizacion', 'tierras')) AS fail_especialidad,
    (NULLIF(TRIM(CAST(src.activo AS STRING)), '') IS NOT NULL AND TRIM(CAST(src.activo AS STRING)) NOT IN ('0', '1', 'False', 'True', 'false', 'true')) AS fail_activo
  FROM src
),
flagged AS (
  SELECT
    *,
    CASE
      WHEN fail_especialidad OR fail_activo THEN 'cast_fallido'
      WHEN cuadrilla_id IS NULL OR cuadrilla_nombre IS NULL OR especialidad IS NULL OR obra_id IS NULL OR activo IS NULL THEN 'nulo_obligatorio'
      ELSE NULL
    END AS motivo_base,
    CASE
      WHEN fail_especialidad THEN 'especialidad'
      WHEN fail_activo THEN 'activo'
      WHEN cuadrilla_id IS NULL THEN 'cuadrilla_id'
      WHEN cuadrilla_nombre IS NULL THEN 'cuadrilla_nombre'
      WHEN especialidad IS NULL THEN 'especialidad'
      WHEN obra_id IS NULL THEN 'obra_id'
      WHEN activo IS NULL THEN 'activo'
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
        IF(motivo_base IS NULL, cuadrilla_id, NULL)
        ORDER BY cuadrilla_id
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
  raw_cuadrilla_id AS cuadrilla_id,
  raw_cuadrilla_nombre AS cuadrilla_nombre,
  raw_especialidad AS especialidad,
  raw_obra_id AS obra_id,
  raw_activo AS activo,
  motivo,
  regla
FROM resolved
WHERE motivo IS NOT NULL;

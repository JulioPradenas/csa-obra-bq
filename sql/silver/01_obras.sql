-- csa_silver.obras y csa_silver.q_obras
-- prioridad: cast_fallido > nulo_obligatorio > duplicado > fk_huerfana > fecha_incoherente
-- SAFE_CAST, TRIM, ROW_NUMBER. La FK mira la dimensión silver ya limpia.
-- BigQuery: EXTRACT(DAYOFWEEK) usa 1 = domingo, así que el lunes es 2.
-- Lab de portafolio. Marca con fines ilustrativos.

CREATE OR REPLACE TABLE `csa_silver.obras`
OPTIONS (
  description="Silver obras. Lab de portafolio. Marca con fines ilustrativos. Tipado con SAFE_CAST, una fila por llave natural, FK contra silver. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
WITH src AS (
  SELECT * FROM `csa_bronze.obras`
),
typed AS (
  SELECT
    src.obra_id AS raw_obra_id,
    src.obra_nombre AS raw_obra_nombre,
    src.comuna AS raw_comuna,
    src.mandante AS raw_mandante,
    src.tipo_obra AS raw_tipo_obra,
    src.estado_obra AS raw_estado_obra,
    src.fecha_inicio AS raw_fecha_inicio,
    src.fecha_termino AS raw_fecha_termino,
    src.activo AS raw_activo,
    NULLIF(UPPER(TRIM(CAST(src.obra_id AS STRING))), '') AS obra_id,
    NULLIF(TRIM(CAST(src.obra_nombre AS STRING)), '') AS obra_nombre,
    NULLIF(TRIM(CAST(src.comuna AS STRING)), '') AS comuna,
    NULLIF(TRIM(CAST(src.mandante AS STRING)), '') AS mandante,
    NULLIF(LOWER(TRIM(CAST(src.tipo_obra AS STRING))), '') AS tipo_obra,
    NULLIF(LOWER(TRIM(CAST(src.estado_obra AS STRING))), '') AS estado_obra,
    SAFE_CAST(NULLIF(TRIM(CAST(src.fecha_inicio AS STRING)), '') AS DATE) AS fecha_inicio,
    SAFE_CAST(NULLIF(TRIM(CAST(src.fecha_termino AS STRING)), '') AS DATE) AS fecha_termino,
    CASE
        WHEN NULLIF(TRIM(CAST(src.activo AS STRING)), '') IS NULL THEN NULL
        WHEN TRIM(CAST(src.activo AS STRING)) IN ('true', 'True', '1') THEN TRUE
        WHEN TRIM(CAST(src.activo AS STRING)) IN ('false', 'False', '0') THEN FALSE
        ELSE NULL
      END AS activo,
    (NULLIF(TRIM(CAST(src.tipo_obra AS STRING)), '') IS NOT NULL AND LOWER(TRIM(CAST(src.tipo_obra AS STRING))) NOT IN ('aguas_lluvia', 'conservacion', 'pavimentacion', 'puente')) AS fail_tipo_obra,
    (NULLIF(TRIM(CAST(src.estado_obra AS STRING)), '') IS NOT NULL AND LOWER(TRIM(CAST(src.estado_obra AS STRING))) NOT IN ('en_ejecucion', 'paralizada', 'terminada')) AS fail_estado_obra,
    (NULLIF(TRIM(CAST(src.fecha_inicio AS STRING)), '') IS NOT NULL AND SAFE_CAST(NULLIF(TRIM(CAST(src.fecha_inicio AS STRING)), '') AS DATE) IS NULL) AS fail_fecha_inicio,
    (NULLIF(TRIM(CAST(src.fecha_termino AS STRING)), '') IS NOT NULL AND SAFE_CAST(NULLIF(TRIM(CAST(src.fecha_termino AS STRING)), '') AS DATE) IS NULL) AS fail_fecha_termino,
    (NULLIF(TRIM(CAST(src.activo AS STRING)), '') IS NOT NULL AND TRIM(CAST(src.activo AS STRING)) NOT IN ('0', '1', 'False', 'True', 'false', 'true')) AS fail_activo
  FROM src
),
flagged AS (
  SELECT
    *,
    CASE
      WHEN fail_tipo_obra OR fail_estado_obra OR fail_fecha_inicio OR fail_fecha_termino OR fail_activo THEN 'cast_fallido'
      WHEN obra_id IS NULL OR obra_nombre IS NULL OR comuna IS NULL OR mandante IS NULL OR tipo_obra IS NULL OR estado_obra IS NULL OR fecha_inicio IS NULL OR fecha_termino IS NULL OR activo IS NULL THEN 'nulo_obligatorio'
      ELSE NULL
    END AS motivo_base,
    CASE
      WHEN fail_tipo_obra THEN 'tipo_obra'
      WHEN fail_estado_obra THEN 'estado_obra'
      WHEN fail_fecha_inicio THEN 'fecha_inicio'
      WHEN fail_fecha_termino THEN 'fecha_termino'
      WHEN fail_activo THEN 'activo'
      WHEN obra_id IS NULL THEN 'obra_id'
      WHEN obra_nombre IS NULL THEN 'obra_nombre'
      WHEN comuna IS NULL THEN 'comuna'
      WHEN mandante IS NULL THEN 'mandante'
      WHEN tipo_obra IS NULL THEN 'tipo_obra'
      WHEN estado_obra IS NULL THEN 'estado_obra'
      WHEN fecha_inicio IS NULL THEN 'fecha_inicio'
      WHEN fecha_termino IS NULL THEN 'fecha_termino'
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
        IF(motivo_base IS NULL, obra_id, NULL)
        ORDER BY obra_id
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
      WHEN FALSE THEN 'fk_huerfana'
      WHEN ranked.fecha_termino < ranked.fecha_inicio THEN 'fecha_incoherente'
      ELSE NULL
    END AS motivo,
    CASE
      WHEN ranked.motivo_base IS NOT NULL THEN ranked.regla_base
      WHEN ranked.rn > 1 THEN 'llave natural'
      WHEN FALSE THEN 'fk'
      WHEN ranked.fecha_termino < ranked.fecha_inicio THEN 'fecha_termino'
      ELSE NULL
    END AS regla
  FROM ranked
)
SELECT
  obra_id,
  obra_nombre,
  comuna,
  mandante,
  tipo_obra,
  estado_obra,
  fecha_inicio,
  fecha_termino,
  activo
FROM resolved
WHERE motivo IS NULL
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY obra_id
  ORDER BY obra_id
) = 1;

CREATE OR REPLACE TABLE `csa_silver.q_obras`
OPTIONS (
  description="Cuarentena de obras. Lab de portafolio. Marca con fines ilustrativos. Una fila, un motivo, el de mayor prioridad. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
WITH src AS (
  SELECT * FROM `csa_bronze.obras`
),
typed AS (
  SELECT
    src.obra_id AS raw_obra_id,
    src.obra_nombre AS raw_obra_nombre,
    src.comuna AS raw_comuna,
    src.mandante AS raw_mandante,
    src.tipo_obra AS raw_tipo_obra,
    src.estado_obra AS raw_estado_obra,
    src.fecha_inicio AS raw_fecha_inicio,
    src.fecha_termino AS raw_fecha_termino,
    src.activo AS raw_activo,
    NULLIF(UPPER(TRIM(CAST(src.obra_id AS STRING))), '') AS obra_id,
    NULLIF(TRIM(CAST(src.obra_nombre AS STRING)), '') AS obra_nombre,
    NULLIF(TRIM(CAST(src.comuna AS STRING)), '') AS comuna,
    NULLIF(TRIM(CAST(src.mandante AS STRING)), '') AS mandante,
    NULLIF(LOWER(TRIM(CAST(src.tipo_obra AS STRING))), '') AS tipo_obra,
    NULLIF(LOWER(TRIM(CAST(src.estado_obra AS STRING))), '') AS estado_obra,
    SAFE_CAST(NULLIF(TRIM(CAST(src.fecha_inicio AS STRING)), '') AS DATE) AS fecha_inicio,
    SAFE_CAST(NULLIF(TRIM(CAST(src.fecha_termino AS STRING)), '') AS DATE) AS fecha_termino,
    CASE
        WHEN NULLIF(TRIM(CAST(src.activo AS STRING)), '') IS NULL THEN NULL
        WHEN TRIM(CAST(src.activo AS STRING)) IN ('true', 'True', '1') THEN TRUE
        WHEN TRIM(CAST(src.activo AS STRING)) IN ('false', 'False', '0') THEN FALSE
        ELSE NULL
      END AS activo,
    (NULLIF(TRIM(CAST(src.tipo_obra AS STRING)), '') IS NOT NULL AND LOWER(TRIM(CAST(src.tipo_obra AS STRING))) NOT IN ('aguas_lluvia', 'conservacion', 'pavimentacion', 'puente')) AS fail_tipo_obra,
    (NULLIF(TRIM(CAST(src.estado_obra AS STRING)), '') IS NOT NULL AND LOWER(TRIM(CAST(src.estado_obra AS STRING))) NOT IN ('en_ejecucion', 'paralizada', 'terminada')) AS fail_estado_obra,
    (NULLIF(TRIM(CAST(src.fecha_inicio AS STRING)), '') IS NOT NULL AND SAFE_CAST(NULLIF(TRIM(CAST(src.fecha_inicio AS STRING)), '') AS DATE) IS NULL) AS fail_fecha_inicio,
    (NULLIF(TRIM(CAST(src.fecha_termino AS STRING)), '') IS NOT NULL AND SAFE_CAST(NULLIF(TRIM(CAST(src.fecha_termino AS STRING)), '') AS DATE) IS NULL) AS fail_fecha_termino,
    (NULLIF(TRIM(CAST(src.activo AS STRING)), '') IS NOT NULL AND TRIM(CAST(src.activo AS STRING)) NOT IN ('0', '1', 'False', 'True', 'false', 'true')) AS fail_activo
  FROM src
),
flagged AS (
  SELECT
    *,
    CASE
      WHEN fail_tipo_obra OR fail_estado_obra OR fail_fecha_inicio OR fail_fecha_termino OR fail_activo THEN 'cast_fallido'
      WHEN obra_id IS NULL OR obra_nombre IS NULL OR comuna IS NULL OR mandante IS NULL OR tipo_obra IS NULL OR estado_obra IS NULL OR fecha_inicio IS NULL OR fecha_termino IS NULL OR activo IS NULL THEN 'nulo_obligatorio'
      ELSE NULL
    END AS motivo_base,
    CASE
      WHEN fail_tipo_obra THEN 'tipo_obra'
      WHEN fail_estado_obra THEN 'estado_obra'
      WHEN fail_fecha_inicio THEN 'fecha_inicio'
      WHEN fail_fecha_termino THEN 'fecha_termino'
      WHEN fail_activo THEN 'activo'
      WHEN obra_id IS NULL THEN 'obra_id'
      WHEN obra_nombre IS NULL THEN 'obra_nombre'
      WHEN comuna IS NULL THEN 'comuna'
      WHEN mandante IS NULL THEN 'mandante'
      WHEN tipo_obra IS NULL THEN 'tipo_obra'
      WHEN estado_obra IS NULL THEN 'estado_obra'
      WHEN fecha_inicio IS NULL THEN 'fecha_inicio'
      WHEN fecha_termino IS NULL THEN 'fecha_termino'
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
        IF(motivo_base IS NULL, obra_id, NULL)
        ORDER BY obra_id
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
      WHEN FALSE THEN 'fk_huerfana'
      WHEN ranked.fecha_termino < ranked.fecha_inicio THEN 'fecha_incoherente'
      ELSE NULL
    END AS motivo,
    CASE
      WHEN ranked.motivo_base IS NOT NULL THEN ranked.regla_base
      WHEN ranked.rn > 1 THEN 'llave natural'
      WHEN FALSE THEN 'fk'
      WHEN ranked.fecha_termino < ranked.fecha_inicio THEN 'fecha_termino'
      ELSE NULL
    END AS regla
  FROM ranked
)
SELECT
  raw_obra_id AS obra_id,
  raw_obra_nombre AS obra_nombre,
  raw_comuna AS comuna,
  raw_mandante AS mandante,
  raw_tipo_obra AS tipo_obra,
  raw_estado_obra AS estado_obra,
  raw_fecha_inicio AS fecha_inicio,
  raw_fecha_termino AS fecha_termino,
  raw_activo AS activo,
  motivo,
  regla
FROM resolved
WHERE motivo IS NOT NULL;

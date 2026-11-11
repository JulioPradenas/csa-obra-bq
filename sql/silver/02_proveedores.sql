-- csa_silver.proveedores y csa_silver.q_proveedores
-- prioridad: cast_fallido > nulo_obligatorio > duplicado > fk_huerfana > fecha_incoherente
-- SAFE_CAST, TRIM, ROW_NUMBER. La FK mira la dimensión silver ya limpia.
-- BigQuery: EXTRACT(DAYOFWEEK) usa 1 = domingo, así que el lunes es 2.
-- Lab de portafolio. Marca con fines ilustrativos.

CREATE OR REPLACE TABLE `csa_silver.proveedores`
OPTIONS (
  description="Silver proveedores. Lab de portafolio. Marca con fines ilustrativos. Tipado con SAFE_CAST, una fila por llave natural, FK contra silver. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
WITH src AS (
  SELECT * FROM `csa_bronze.proveedores`
),
typed AS (
  SELECT
    src.proveedor_id AS raw_proveedor_id,
    src.proveedor_nombre AS raw_proveedor_nombre,
    src.rubro AS raw_rubro,
    src.comuna AS raw_comuna,
    src.activo AS raw_activo,
    NULLIF(UPPER(TRIM(CAST(src.proveedor_id AS STRING))), '') AS proveedor_id,
    NULLIF(TRIM(CAST(src.proveedor_nombre AS STRING)), '') AS proveedor_nombre,
    NULLIF(LOWER(TRIM(CAST(src.rubro AS STRING))), '') AS rubro,
    NULLIF(TRIM(CAST(src.comuna AS STRING)), '') AS comuna,
    CASE
        WHEN NULLIF(TRIM(CAST(src.activo AS STRING)), '') IS NULL THEN NULL
        WHEN TRIM(CAST(src.activo AS STRING)) IN ('true', 'True', '1') THEN TRUE
        WHEN TRIM(CAST(src.activo AS STRING)) IN ('false', 'False', '0') THEN FALSE
        ELSE NULL
      END AS activo,
    (NULLIF(TRIM(CAST(src.rubro AS STRING)), '') IS NOT NULL AND LOWER(TRIM(CAST(src.rubro AS STRING))) NOT IN ('acero', 'arido', 'asfalto', 'cemento', 'combustible')) AS fail_rubro,
    (NULLIF(TRIM(CAST(src.activo AS STRING)), '') IS NOT NULL AND TRIM(CAST(src.activo AS STRING)) NOT IN ('0', '1', 'False', 'True', 'false', 'true')) AS fail_activo
  FROM src
),
flagged AS (
  SELECT
    *,
    CASE
      WHEN fail_rubro OR fail_activo THEN 'cast_fallido'
      WHEN proveedor_id IS NULL OR proveedor_nombre IS NULL OR rubro IS NULL OR comuna IS NULL OR activo IS NULL THEN 'nulo_obligatorio'
      ELSE NULL
    END AS motivo_base,
    CASE
      WHEN fail_rubro THEN 'rubro'
      WHEN fail_activo THEN 'activo'
      WHEN proveedor_id IS NULL THEN 'proveedor_id'
      WHEN proveedor_nombre IS NULL THEN 'proveedor_nombre'
      WHEN rubro IS NULL THEN 'rubro'
      WHEN comuna IS NULL THEN 'comuna'
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
        IF(motivo_base IS NULL, proveedor_id, NULL)
        ORDER BY proveedor_id
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
      WHEN FALSE THEN 'fecha_incoherente'
      ELSE NULL
    END AS motivo,
    CASE
      WHEN ranked.motivo_base IS NOT NULL THEN ranked.regla_base
      WHEN ranked.rn > 1 THEN 'llave natural'
      WHEN FALSE THEN 'fk'
      WHEN FALSE THEN 'fecha'
      ELSE NULL
    END AS regla
  FROM ranked
)
SELECT
  proveedor_id,
  proveedor_nombre,
  rubro,
  comuna,
  activo
FROM resolved
WHERE motivo IS NULL
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY proveedor_id
  ORDER BY proveedor_id
) = 1;

CREATE OR REPLACE TABLE `csa_silver.q_proveedores`
OPTIONS (
  description="Cuarentena de proveedores. Lab de portafolio. Marca con fines ilustrativos. Una fila, un motivo, el de mayor prioridad. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
WITH src AS (
  SELECT * FROM `csa_bronze.proveedores`
),
typed AS (
  SELECT
    src.proveedor_id AS raw_proveedor_id,
    src.proveedor_nombre AS raw_proveedor_nombre,
    src.rubro AS raw_rubro,
    src.comuna AS raw_comuna,
    src.activo AS raw_activo,
    NULLIF(UPPER(TRIM(CAST(src.proveedor_id AS STRING))), '') AS proveedor_id,
    NULLIF(TRIM(CAST(src.proveedor_nombre AS STRING)), '') AS proveedor_nombre,
    NULLIF(LOWER(TRIM(CAST(src.rubro AS STRING))), '') AS rubro,
    NULLIF(TRIM(CAST(src.comuna AS STRING)), '') AS comuna,
    CASE
        WHEN NULLIF(TRIM(CAST(src.activo AS STRING)), '') IS NULL THEN NULL
        WHEN TRIM(CAST(src.activo AS STRING)) IN ('true', 'True', '1') THEN TRUE
        WHEN TRIM(CAST(src.activo AS STRING)) IN ('false', 'False', '0') THEN FALSE
        ELSE NULL
      END AS activo,
    (NULLIF(TRIM(CAST(src.rubro AS STRING)), '') IS NOT NULL AND LOWER(TRIM(CAST(src.rubro AS STRING))) NOT IN ('acero', 'arido', 'asfalto', 'cemento', 'combustible')) AS fail_rubro,
    (NULLIF(TRIM(CAST(src.activo AS STRING)), '') IS NOT NULL AND TRIM(CAST(src.activo AS STRING)) NOT IN ('0', '1', 'False', 'True', 'false', 'true')) AS fail_activo
  FROM src
),
flagged AS (
  SELECT
    *,
    CASE
      WHEN fail_rubro OR fail_activo THEN 'cast_fallido'
      WHEN proveedor_id IS NULL OR proveedor_nombre IS NULL OR rubro IS NULL OR comuna IS NULL OR activo IS NULL THEN 'nulo_obligatorio'
      ELSE NULL
    END AS motivo_base,
    CASE
      WHEN fail_rubro THEN 'rubro'
      WHEN fail_activo THEN 'activo'
      WHEN proveedor_id IS NULL THEN 'proveedor_id'
      WHEN proveedor_nombre IS NULL THEN 'proveedor_nombre'
      WHEN rubro IS NULL THEN 'rubro'
      WHEN comuna IS NULL THEN 'comuna'
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
        IF(motivo_base IS NULL, proveedor_id, NULL)
        ORDER BY proveedor_id
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
      WHEN FALSE THEN 'fecha_incoherente'
      ELSE NULL
    END AS motivo,
    CASE
      WHEN ranked.motivo_base IS NOT NULL THEN ranked.regla_base
      WHEN ranked.rn > 1 THEN 'llave natural'
      WHEN FALSE THEN 'fk'
      WHEN FALSE THEN 'fecha'
      ELSE NULL
    END AS regla
  FROM ranked
)
SELECT
  raw_proveedor_id AS proveedor_id,
  raw_proveedor_nombre AS proveedor_nombre,
  raw_rubro AS rubro,
  raw_comuna AS comuna,
  raw_activo AS activo,
  motivo,
  regla
FROM resolved
WHERE motivo IS NOT NULL;

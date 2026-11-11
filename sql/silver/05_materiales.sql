-- csa_silver.materiales y csa_silver.q_materiales
-- prioridad: cast_fallido > nulo_obligatorio > duplicado > fk_huerfana > fecha_incoherente
-- SAFE_CAST, TRIM, ROW_NUMBER. La FK mira la dimensión silver ya limpia.
-- BigQuery: EXTRACT(DAYOFWEEK) usa 1 = domingo, así que el lunes es 2.
-- Lab de portafolio. Marca con fines ilustrativos.

CREATE OR REPLACE TABLE `csa_silver.materiales`
OPTIONS (
  description="Silver materiales. Lab de portafolio. Marca con fines ilustrativos. Tipado con SAFE_CAST, una fila por llave natural, FK contra silver. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
WITH src AS (
  SELECT * FROM `csa_bronze.materiales`
),
typed AS (
  SELECT
    src.material_id AS raw_material_id,
    src.material_nombre AS raw_material_nombre,
    src.familia AS raw_familia,
    src.unidad_medida AS raw_unidad_medida,
    src.precio_unitario AS raw_precio_unitario,
    src.proveedor_id AS raw_proveedor_id,
    NULLIF(UPPER(TRIM(CAST(src.material_id AS STRING))), '') AS material_id,
    NULLIF(TRIM(CAST(src.material_nombre AS STRING)), '') AS material_nombre,
    NULLIF(LOWER(TRIM(CAST(src.familia AS STRING))), '') AS familia,
    NULLIF(LOWER(TRIM(CAST(src.unidad_medida AS STRING))), '') AS unidad_medida,
    SAFE_CAST(NULLIF(TRIM(CAST(src.precio_unitario AS STRING)), '') AS NUMERIC) AS precio_unitario,
    NULLIF(UPPER(TRIM(CAST(src.proveedor_id AS STRING))), '') AS proveedor_id,
    (NULLIF(TRIM(CAST(src.familia AS STRING)), '') IS NOT NULL AND LOWER(TRIM(CAST(src.familia AS STRING))) NOT IN ('acero', 'arido', 'asfalto', 'cemento', 'combustible')) AS fail_familia,
    (NULLIF(TRIM(CAST(src.unidad_medida AS STRING)), '') IS NOT NULL AND LOWER(TRIM(CAST(src.unidad_medida AS STRING))) NOT IN ('kg', 'l', 'm2', 'm3', 'ml', 'ton', 'un')) AS fail_unidad_medida,
    (NULLIF(TRIM(CAST(src.precio_unitario AS STRING)), '') IS NOT NULL AND SAFE_CAST(NULLIF(TRIM(CAST(src.precio_unitario AS STRING)), '') AS NUMERIC) IS NULL) AS fail_precio_unitario
  FROM src
),
flagged AS (
  SELECT
    *,
    CASE
      WHEN fail_familia OR fail_unidad_medida OR fail_precio_unitario THEN 'cast_fallido'
      WHEN material_id IS NULL OR material_nombre IS NULL OR familia IS NULL OR unidad_medida IS NULL OR precio_unitario IS NULL OR proveedor_id IS NULL THEN 'nulo_obligatorio'
      ELSE NULL
    END AS motivo_base,
    CASE
      WHEN fail_familia THEN 'familia'
      WHEN fail_unidad_medida THEN 'unidad_medida'
      WHEN fail_precio_unitario THEN 'precio_unitario'
      WHEN material_id IS NULL THEN 'material_id'
      WHEN material_nombre IS NULL THEN 'material_nombre'
      WHEN familia IS NULL THEN 'familia'
      WHEN unidad_medida IS NULL THEN 'unidad_medida'
      WHEN precio_unitario IS NULL THEN 'precio_unitario'
      WHEN proveedor_id IS NULL THEN 'proveedor_id'
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
        IF(motivo_base IS NULL, material_id, NULL)
        ORDER BY material_id
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
      WHEN dim_proveedores.proveedor_id IS NULL THEN 'fk_huerfana'
      WHEN FALSE THEN 'fecha_incoherente'
      ELSE NULL
    END AS motivo,
    CASE
      WHEN ranked.motivo_base IS NOT NULL THEN ranked.regla_base
      WHEN ranked.rn > 1 THEN 'llave natural'
      WHEN dim_proveedores.proveedor_id IS NULL THEN 'proveedor_id'
      WHEN FALSE THEN 'fecha'
      ELSE NULL
    END AS regla
  FROM ranked
  LEFT JOIN `csa_silver.proveedores` AS dim_proveedores
      ON ranked.proveedor_id = dim_proveedores.proveedor_id
)
SELECT
  material_id,
  material_nombre,
  familia,
  unidad_medida,
  precio_unitario,
  proveedor_id
FROM resolved
WHERE motivo IS NULL
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY material_id
  ORDER BY material_id
) = 1;

CREATE OR REPLACE TABLE `csa_silver.q_materiales`
OPTIONS (
  description="Cuarentena de materiales. Lab de portafolio. Marca con fines ilustrativos. Una fila, un motivo, el de mayor prioridad. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
WITH src AS (
  SELECT * FROM `csa_bronze.materiales`
),
typed AS (
  SELECT
    src.material_id AS raw_material_id,
    src.material_nombre AS raw_material_nombre,
    src.familia AS raw_familia,
    src.unidad_medida AS raw_unidad_medida,
    src.precio_unitario AS raw_precio_unitario,
    src.proveedor_id AS raw_proveedor_id,
    NULLIF(UPPER(TRIM(CAST(src.material_id AS STRING))), '') AS material_id,
    NULLIF(TRIM(CAST(src.material_nombre AS STRING)), '') AS material_nombre,
    NULLIF(LOWER(TRIM(CAST(src.familia AS STRING))), '') AS familia,
    NULLIF(LOWER(TRIM(CAST(src.unidad_medida AS STRING))), '') AS unidad_medida,
    SAFE_CAST(NULLIF(TRIM(CAST(src.precio_unitario AS STRING)), '') AS NUMERIC) AS precio_unitario,
    NULLIF(UPPER(TRIM(CAST(src.proveedor_id AS STRING))), '') AS proveedor_id,
    (NULLIF(TRIM(CAST(src.familia AS STRING)), '') IS NOT NULL AND LOWER(TRIM(CAST(src.familia AS STRING))) NOT IN ('acero', 'arido', 'asfalto', 'cemento', 'combustible')) AS fail_familia,
    (NULLIF(TRIM(CAST(src.unidad_medida AS STRING)), '') IS NOT NULL AND LOWER(TRIM(CAST(src.unidad_medida AS STRING))) NOT IN ('kg', 'l', 'm2', 'm3', 'ml', 'ton', 'un')) AS fail_unidad_medida,
    (NULLIF(TRIM(CAST(src.precio_unitario AS STRING)), '') IS NOT NULL AND SAFE_CAST(NULLIF(TRIM(CAST(src.precio_unitario AS STRING)), '') AS NUMERIC) IS NULL) AS fail_precio_unitario
  FROM src
),
flagged AS (
  SELECT
    *,
    CASE
      WHEN fail_familia OR fail_unidad_medida OR fail_precio_unitario THEN 'cast_fallido'
      WHEN material_id IS NULL OR material_nombre IS NULL OR familia IS NULL OR unidad_medida IS NULL OR precio_unitario IS NULL OR proveedor_id IS NULL THEN 'nulo_obligatorio'
      ELSE NULL
    END AS motivo_base,
    CASE
      WHEN fail_familia THEN 'familia'
      WHEN fail_unidad_medida THEN 'unidad_medida'
      WHEN fail_precio_unitario THEN 'precio_unitario'
      WHEN material_id IS NULL THEN 'material_id'
      WHEN material_nombre IS NULL THEN 'material_nombre'
      WHEN familia IS NULL THEN 'familia'
      WHEN unidad_medida IS NULL THEN 'unidad_medida'
      WHEN precio_unitario IS NULL THEN 'precio_unitario'
      WHEN proveedor_id IS NULL THEN 'proveedor_id'
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
        IF(motivo_base IS NULL, material_id, NULL)
        ORDER BY material_id
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
      WHEN dim_proveedores.proveedor_id IS NULL THEN 'fk_huerfana'
      WHEN FALSE THEN 'fecha_incoherente'
      ELSE NULL
    END AS motivo,
    CASE
      WHEN ranked.motivo_base IS NOT NULL THEN ranked.regla_base
      WHEN ranked.rn > 1 THEN 'llave natural'
      WHEN dim_proveedores.proveedor_id IS NULL THEN 'proveedor_id'
      WHEN FALSE THEN 'fecha'
      ELSE NULL
    END AS regla
  FROM ranked
  LEFT JOIN `csa_silver.proveedores` AS dim_proveedores
      ON ranked.proveedor_id = dim_proveedores.proveedor_id
)
SELECT
  raw_material_id AS material_id,
  raw_material_nombre AS material_nombre,
  raw_familia AS familia,
  raw_unidad_medida AS unidad_medida,
  raw_precio_unitario AS precio_unitario,
  raw_proveedor_id AS proveedor_id,
  motivo,
  regla
FROM resolved
WHERE motivo IS NOT NULL;

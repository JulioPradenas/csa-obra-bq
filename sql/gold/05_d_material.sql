-- d_material. Grano: 1 material. CLUSTER BY material_id, proveedor_id. Sin partición por fecha.
-- Lab de portafolio. Marca con fines ilustrativos.

CREATE OR REPLACE TABLE `csa_gold.d_material`
CLUSTER BY material_id, proveedor_id
OPTIONS (
  description="Dimensión material. Lab de portafolio. Marca con fines ilustrativos. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
SELECT
  material_id,
  material_nombre,
  familia,
  unidad_medida,
  CASE unidad_medida
    WHEN 'm3' THEN 'm³'
    WHEN 'm2' THEN 'm²'
    WHEN 'ml' THEN 'ml'
    WHEN 'kg' THEN 'kg'
    WHEN 'ton' THEN 't'
    WHEN 'l' THEN 'L'
    WHEN 'un' THEN 'un'
  END AS unidad_nombre,
  precio_unitario,
  proveedor_id
FROM `csa_silver.materiales`;

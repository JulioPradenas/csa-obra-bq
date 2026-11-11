-- d_proveedor. Grano: 1 proveedor. CLUSTER BY proveedor_id. Sin partición por fecha.
-- Lab de portafolio. Marca con fines ilustrativos.

CREATE OR REPLACE TABLE `csa_gold.d_proveedor`
CLUSTER BY proveedor_id
OPTIONS (
  description="Dimensión proveedor. Lab de portafolio. Marca con fines ilustrativos. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
SELECT
  proveedor_id,
  proveedor_nombre,
  rubro,
  comuna,
  activo
FROM `csa_silver.proveedores`;

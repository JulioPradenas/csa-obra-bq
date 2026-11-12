-- d_cuadrilla. Grano: 1 cuadrilla. CLUSTER BY obra_id, cuadrilla_id. Sin partición por fecha.
-- Lab de portafolio. Marca con fines ilustrativos.

CREATE OR REPLACE TABLE `csa_gold.d_cuadrilla`
CLUSTER BY obra_id, cuadrilla_id
OPTIONS (
  description="Dimensión cuadrilla. Lab de portafolio. Marca con fines ilustrativos. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
SELECT
  cuadrilla_id,
  cuadrilla_nombre,
  especialidad,
  obra_id,
  activo
FROM `csa_silver.cuadrillas`;

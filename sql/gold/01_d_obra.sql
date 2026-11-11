-- d_obra. Grano: 1 obra. CLUSTER BY obra_id. Sin partición por fecha.
-- Lab de portafolio. Marca con fines ilustrativos.

CREATE OR REPLACE TABLE `csa_gold.d_obra`
CLUSTER BY obra_id
OPTIONS (
  description="Dimensión obra. Lab de portafolio. Marca con fines ilustrativos. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
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
FROM `csa_silver.obras`;

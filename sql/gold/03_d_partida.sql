-- d_partida. Grano: 1 partida. CLUSTER BY obra_id, partida_id. Sin partición por fecha.
-- monto_contrato vive aquí, una vez. No se copia en cada semana del hecho.
-- Lab de portafolio. Marca con fines ilustrativos.

CREATE OR REPLACE TABLE `csa_gold.d_partida`
CLUSTER BY obra_id, partida_id
OPTIONS (
  description="Dimensión partida. Lab de portafolio. Marca con fines ilustrativos. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
SELECT
  partida_id,
  obra_id,
  codigo_partida,
  partida_nombre,
  capitulo,
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
  cantidad_contrato,
  precio_unitario,
  cantidad_contrato * precio_unitario AS monto_contrato,
  hh_teorica_por_unidad
FROM `csa_silver.partidas`;

-- f_consumo_material. Grano: obra × material × semana.
-- CLUSTER BY obra_id, material_id. Sin partición por fecha.
-- Montos aditivos. La desviación no se guarda en la fila.
-- Lab de portafolio. Marca con fines ilustrativos.

CREATE OR REPLACE TABLE `csa_gold.f_consumo_material`
CLUSTER BY obra_id, material_id
OPTIONS (
  description="Hecho consumo semanal. Lab de portafolio. Marca con fines ilustrativos. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
WITH unido AS (
  SELECT
    COALESCE(presupuesto.obra_id, vale.obra_id) AS obra_id,
    COALESCE(presupuesto.material_id, vale.material_id) AS material_id,
    COALESCE(presupuesto.semana_lunes, vale.semana_lunes) AS semana_lunes,
    IFNULL(presupuesto.cantidad_presupuestada, 0) AS cantidad_presupuestada,
    IFNULL(vale.cantidad_real, 0) AS cantidad_real
  FROM `csa_silver.presupuesto_material` AS presupuesto
  FULL OUTER JOIN `csa_silver.vale_consumo` AS vale
    ON presupuesto.obra_id = vale.obra_id
    AND presupuesto.material_id = vale.material_id
    AND presupuesto.semana_lunes = vale.semana_lunes
)
SELECT
  unido.obra_id,
  unido.material_id,
  unido.semana_lunes,
  unido.cantidad_presupuestada,
  unido.cantidad_real,
  material.precio_unitario,
  unido.cantidad_presupuestada * material.precio_unitario AS monto_presupuestado,
  unido.cantidad_real * material.precio_unitario AS monto_real
FROM unido
INNER JOIN `csa_gold.d_material` AS material
  ON unido.material_id = material.material_id;

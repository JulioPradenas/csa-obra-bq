-- v_consumo_semana. Fuente de Looker Studio para Materiales y desviación.
-- Grano: obra × material × semana (igual que f_consumo_material), con familia
-- legible y proveedor. Montos a precio de presupuesto.
-- Lab de portafolio. Marca con fines ilustrativos.

CREATE OR REPLACE VIEW `csa_gold.v_consumo_semana`
OPTIONS (description="Vista para Looker Studio: consumo semanal de materiales con proveedor. Lab de portafolio. Marca con fines ilustrativos.")
AS
SELECT
  consumo.obra_id,
  obra.obra_nombre,
  consumo.material_id,
  material.material_nombre,
  CASE material.familia
    WHEN 'asfalto' THEN 'Asfalto'
    WHEN 'acero' THEN 'Acero'
    WHEN 'arido' THEN 'Árido'
    WHEN 'cemento' THEN 'Cemento'
    WHEN 'combustible' THEN 'Combustible'
    ELSE material.familia
  END AS familia,
  proveedor.proveedor_nombre,
  material.unidad_nombre AS unidad,
  consumo.semana_lunes,
  consumo.cantidad_presupuestada,
  consumo.cantidad_real,
  consumo.monto_presupuestado,
  consumo.monto_real
FROM `csa_gold.f_consumo_material` AS consumo
INNER JOIN `csa_gold.d_obra` AS obra
  ON consumo.obra_id = obra.obra_id
INNER JOIN `csa_gold.d_material` AS material
  ON consumo.material_id = material.material_id
INNER JOIN `csa_gold.d_proveedor` AS proveedor
  ON material.proveedor_id = proveedor.proveedor_id;

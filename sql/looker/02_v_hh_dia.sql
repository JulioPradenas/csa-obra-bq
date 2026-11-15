-- v_hh_dia. Fuente de Looker Studio para Productividad HH.
-- Grano: obra × cuadrilla × día (igual que f_hh_cuadrilla), con la partida, su
-- unidad y su HH teórica. cuadrilla_etiqueta = «Tierras 01 · Los Batros».
-- Lab de portafolio. Marca con fines ilustrativos.

CREATE OR REPLACE VIEW `csa_gold.v_hh_dia`
OPTIONS (description="Vista para Looker Studio: parte diario de HH con partida y cuadrilla. Lab de portafolio. Marca con fines ilustrativos.")
AS
SELECT
  hh.obra_id,
  obra.obra_nombre,
  hh.cuadrilla_id,
  cuadrilla.cuadrilla_nombre,
  cuadrilla.especialidad,
  CONCAT(
    INITCAP(cuadrilla.especialidad), ' ', RIGHT(cuadrilla.cuadrilla_nombre, 2), ' · ',
    CASE hh.obra_id
      WHEN 'OBR-01' THEN 'Los Batros'
      WHEN 'OBR-02' THEN 'Talcahuano'
      WHEN 'OBR-03' THEN 'Nonguén'
      WHEN 'OBR-04' THEN 'Michaihue'
      WHEN 'OBR-05' THEN 'Coronel'
      WHEN 'OBR-06' THEN 'Hualpén'
      WHEN 'OBR-07' THEN 'Los Ángeles'
      ELSE obra.obra_nombre
    END
  ) AS cuadrilla_etiqueta,
  hh.partida_id,
  partida.partida_nombre,
  partida.unidad_nombre AS unidad,
  partida.hh_teorica_por_unidad AS hh_teorica,
  hh.fecha,
  hh.hh,
  hh.cantidad_ejecutada
FROM `csa_gold.f_hh_cuadrilla` AS hh
INNER JOIN `csa_gold.d_obra` AS obra
  ON hh.obra_id = obra.obra_id
INNER JOIN `csa_gold.d_cuadrilla` AS cuadrilla
  ON hh.cuadrilla_id = cuadrilla.cuadrilla_id
INNER JOIN `csa_gold.d_partida` AS partida
  ON hh.partida_id = partida.partida_id
  AND hh.obra_id = partida.obra_id;

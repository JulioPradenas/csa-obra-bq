-- v_avance_semana. Fuente de Looker Studio para Resumen de obras y Avance vs programa.
-- Grano: obra × partida × semana (igual que f_avance_partida), con nombres legibles.
-- monto_contrato va solo en la primera semana de cada partida (0 en las demás):
-- así SUM(monto_contrato) cuenta el contrato una vez por partida, mientras el
-- período empiece en la primera semana (04/05/2026).
-- Lab de portafolio. Marca con fines ilustrativos.

CREATE OR REPLACE VIEW `csa_gold.v_avance_semana`
OPTIONS (description="Vista para Looker Studio: avance semanal con nombres legibles. Lab de portafolio. Marca con fines ilustrativos.")
AS
SELECT
  avance.obra_id,
  obra.obra_nombre,
  obra.comuna,
  CASE obra.estado_obra
    WHEN 'en_ejecucion' THEN 'En ejecución'
    WHEN 'paralizada' THEN 'Paralizada'
    ELSE obra.estado_obra
  END AS estado_obra,
  avance.partida_id,
  partida.partida_nombre,
  CASE partida.capitulo
    WHEN 'movimiento_tierras' THEN 'Movimiento de tierras'
    WHEN 'pavimentos' THEN 'Pavimentos'
    WHEN 'drenaje' THEN 'Drenaje'
    WHEN 'obras_arte' THEN 'Obras de arte'
    WHEN 'senalizacion' THEN 'Señalización'
    ELSE partida.capitulo
  END AS capitulo,
  partida.unidad_nombre AS unidad,
  avance.semana_lunes,
  avance.cantidad_programada,
  avance.cantidad_ejecutada,
  avance.monto_programado,
  avance.monto_ejecutado,
  IF(
    avance.semana_lunes = MIN(avance.semana_lunes) OVER (PARTITION BY avance.obra_id, avance.partida_id),
    partida.monto_contrato,
    0
  ) AS monto_contrato
FROM `csa_gold.f_avance_partida` AS avance
INNER JOIN `csa_gold.d_obra` AS obra
  ON avance.obra_id = obra.obra_id
INNER JOIN `csa_gold.d_partida` AS partida
  ON avance.partida_id = partida.partida_id
  AND avance.obra_id = partida.obra_id;

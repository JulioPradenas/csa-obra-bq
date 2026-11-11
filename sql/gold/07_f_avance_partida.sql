-- f_avance_partida. Grano: obra × partida × semana.
-- CLUSTER BY obra_id, partida_id. Sin partición por fecha.
-- Montos aditivos. El SPI y el % avance no se guardan en la fila.
-- Lab de portafolio. Marca con fines ilustrativos.

CREATE OR REPLACE TABLE `csa_gold.f_avance_partida`
CLUSTER BY obra_id, partida_id
OPTIONS (
  description="Hecho avance semanal. Lab de portafolio. Marca con fines ilustrativos. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
WITH unido AS (
  SELECT
    COALESCE(programado.obra_id, ejecutado.obra_id) AS obra_id,
    COALESCE(programado.partida_id, ejecutado.partida_id) AS partida_id,
    COALESCE(programado.semana_lunes, ejecutado.semana_lunes) AS semana_lunes,
    IFNULL(programado.cantidad_programada, 0) AS cantidad_programada,
    IFNULL(ejecutado.cantidad_ejecutada, 0) AS cantidad_ejecutada
  FROM `csa_silver.programa_avance` AS programado
  FULL OUTER JOIN `csa_silver.medicion_avance` AS ejecutado
    ON programado.obra_id = ejecutado.obra_id
    AND programado.partida_id = ejecutado.partida_id
    AND programado.semana_lunes = ejecutado.semana_lunes
)
SELECT
  unido.obra_id,
  unido.partida_id,
  unido.semana_lunes,
  unido.cantidad_programada,
  unido.cantidad_ejecutada,
  partida.precio_unitario,
  unido.cantidad_programada * partida.precio_unitario AS monto_programado,
  unido.cantidad_ejecutada * partida.precio_unitario AS monto_ejecutado
FROM unido
INNER JOIN `csa_gold.d_partida` AS partida
  ON unido.partida_id = partida.partida_id
  AND unido.obra_id = partida.obra_id;

-- f_hh_cuadrilla. Grano: obra × cuadrilla × día.
-- CLUSTER BY obra_id, cuadrilla_id. Sin partición por fecha.
-- HH y cantidad aditivas. El rendimiento se calcula en el gráfico, no en la fila.
-- Lab de portafolio. Marca con fines ilustrativos.

CREATE OR REPLACE TABLE `csa_gold.f_hh_cuadrilla`
CLUSTER BY obra_id, cuadrilla_id
OPTIONS (
  description="Hecho parte diario. Lab de portafolio. Marca con fines ilustrativos. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
SELECT
  obra_id,
  cuadrilla_id,
  partida_id,
  fecha,
  hh,
  cantidad_ejecutada
FROM `csa_silver.parte_hh`;

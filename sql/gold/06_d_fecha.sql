-- d_fecha. Grano: 1 día. CLUSTER BY fecha. Sin partición por fecha.
-- Calendario desde el inicio más temprano hasta el término más tardío de las obras silver.
-- Lab de portafolio. Marca con fines ilustrativos.

CREATE OR REPLACE TABLE `csa_gold.d_fecha`
CLUSTER BY fecha
OPTIONS (
  description="Calendario. Lab de portafolio. Marca con fines ilustrativos. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
WITH limites AS (
  SELECT
    MIN(fecha_inicio) AS inicio,
    MAX(fecha_termino) AS termino
  FROM `csa_silver.obras`
)
SELECT
  dia AS fecha,
  EXTRACT(YEAR FROM dia) AS anio,
  EXTRACT(MONTH FROM dia) AS mes,
  CASE EXTRACT(MONTH FROM dia)
    WHEN 1 THEN 'enero'
    WHEN 2 THEN 'febrero'
    WHEN 3 THEN 'marzo'
    WHEN 4 THEN 'abril'
    WHEN 5 THEN 'mayo'
    WHEN 6 THEN 'junio'
    WHEN 7 THEN 'julio'
    WHEN 8 THEN 'agosto'
    WHEN 9 THEN 'septiembre'
    WHEN 10 THEN 'octubre'
    WHEN 11 THEN 'noviembre'
    WHEN 12 THEN 'diciembre'
  END AS mes_nombre,
  EXTRACT(ISOWEEK FROM dia) AS semana_iso,
  DATE_TRUNC(dia, WEEK(MONDAY)) AS lunes_semana,
  CASE EXTRACT(DAYOFWEEK FROM dia)
    WHEN 2 THEN 'lunes'
    WHEN 3 THEN 'martes'
    WHEN 4 THEN 'miércoles'
    WHEN 5 THEN 'jueves'
    WHEN 6 THEN 'viernes'
    WHEN 7 THEN 'sábado'
    WHEN 1 THEN 'domingo'
  END AS nombre_dia,
  EXTRACT(DAYOFWEEK FROM dia) IN (1, 7) AS es_fin_de_semana
FROM limites
CROSS JOIN UNNEST(GENERATE_DATE_ARRAY(inicio, termino)) AS dia;

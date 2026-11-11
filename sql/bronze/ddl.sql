-- CSA Obra — DDL bronze (landing crudo, todo STRING NULLABLE).
-- Dataset: csa_bronze · location: US · expiración: 60 días.
-- Sandbox sin facturación: sin DML y sin streaming. Este archivo solo tiene
-- CREATE OR REPLACE TABLE. Los CSV entran por load job WRITE_TRUNCATE
-- con max_bad_records=0. No hay ALTER.
--
-- Todas las columnas son STRING. Un BOOL/DATE/TIMESTAMP en el load rechaza
-- el token 'NO-CAST' y el job falla entero (incidente de Meli). Silver
-- castea con SAFE_CAST.
--
-- Lab de portafolio. Marca con fines ilustrativos.

CREATE OR REPLACE TABLE `csa_bronze.obras` (
  obra_id STRING,
  obra_nombre STRING,
  comuna STRING,
  mandante STRING,
  tipo_obra STRING,
  estado_obra STRING,
  fecha_inicio STRING,
  fecha_termino STRING,
  activo STRING
)
OPTIONS (
  description="Bronze obras. Lab de portafolio. Marca con fines ilustrativos. Landing NULLABLE; la tabla expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
);

CREATE OR REPLACE TABLE `csa_bronze.proveedores` (
  proveedor_id STRING,
  proveedor_nombre STRING,
  rubro STRING,
  comuna STRING,
  activo STRING
)
OPTIONS (
  description="Bronze proveedores. Lab de portafolio. Marca con fines ilustrativos. Landing NULLABLE; la tabla expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
);

CREATE OR REPLACE TABLE `csa_bronze.partidas` (
  partida_id STRING,
  obra_id STRING,
  codigo_partida STRING,
  partida_nombre STRING,
  capitulo STRING,
  unidad_medida STRING,
  cantidad_contrato STRING,
  precio_unitario STRING,
  hh_teorica_por_unidad STRING
)
OPTIONS (
  description="Bronze partidas. Lab de portafolio. Marca con fines ilustrativos. Landing NULLABLE; la tabla expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
);

CREATE OR REPLACE TABLE `csa_bronze.cuadrillas` (
  cuadrilla_id STRING,
  cuadrilla_nombre STRING,
  especialidad STRING,
  obra_id STRING,
  activo STRING
)
OPTIONS (
  description="Bronze cuadrillas. Lab de portafolio. Marca con fines ilustrativos. Landing NULLABLE; la tabla expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
);

CREATE OR REPLACE TABLE `csa_bronze.materiales` (
  material_id STRING,
  material_nombre STRING,
  familia STRING,
  unidad_medida STRING,
  precio_unitario STRING,
  proveedor_id STRING
)
OPTIONS (
  description="Bronze materiales. Lab de portafolio. Marca con fines ilustrativos. Landing NULLABLE; la tabla expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
);

CREATE OR REPLACE TABLE `csa_bronze.programa_avance` (
  programa_id STRING,
  obra_id STRING,
  partida_id STRING,
  semana_lunes STRING,
  cantidad_programada STRING
)
OPTIONS (
  description="Bronze programa_avance. Lab de portafolio. Marca con fines ilustrativos. Landing NULLABLE; la tabla expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
);

CREATE OR REPLACE TABLE `csa_bronze.medicion_avance` (
  medicion_id STRING,
  obra_id STRING,
  partida_id STRING,
  semana_lunes STRING,
  cantidad_ejecutada STRING
)
OPTIONS (
  description="Bronze medicion_avance. Lab de portafolio. Marca con fines ilustrativos. Landing NULLABLE; la tabla expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
);

CREATE OR REPLACE TABLE `csa_bronze.parte_hh` (
  parte_id STRING,
  obra_id STRING,
  cuadrilla_id STRING,
  partida_id STRING,
  fecha STRING,
  hh STRING,
  cantidad_ejecutada STRING
)
OPTIONS (
  description="Bronze parte_hh. Lab de portafolio. Marca con fines ilustrativos. Landing NULLABLE; la tabla expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
);

CREATE OR REPLACE TABLE `csa_bronze.presupuesto_material` (
  presupuesto_id STRING,
  obra_id STRING,
  material_id STRING,
  semana_lunes STRING,
  cantidad_presupuestada STRING
)
OPTIONS (
  description="Bronze presupuesto_material. Lab de portafolio. Marca con fines ilustrativos. Landing NULLABLE; la tabla expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
);

CREATE OR REPLACE TABLE `csa_bronze.vale_consumo` (
  vale_id STRING,
  obra_id STRING,
  material_id STRING,
  semana_lunes STRING,
  cantidad_real STRING
)
OPTIONS (
  description="Bronze vale_consumo. Lab de portafolio. Marca con fines ilustrativos. Landing NULLABLE; la tabla expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
);

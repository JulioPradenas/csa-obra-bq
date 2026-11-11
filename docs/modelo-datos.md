# Modelo de datos — CSA Obra

> **Lab de portafolio. Marca con fines ilustrativos.**  
> Obra vial ambientada en el Gran Concepción, inspirada en el rubro de Ingeniería CSA (San Pedro de la Paz). Sin logos y sin datos reales de la marca.

**Analista:** Julio Pradenas  
**Repo:** `csa-obra-bq`  
**Paso:** 1 fijó la forma. El Paso 2 materializa el CSV y el bronze; el contrato de grano no cambia.

Este documento es el contrato de grano y de métricas. Si una fórmula cambia, se cambia aquí primero. El dashboard futuro lee gold. Bronze y la cuarentena no entran a un KPI.

---

## 1. Objetivo

Responder, con un solo número por KPI, cómo va la obra contra el programa, cuántas horas hombre (HH) se van por unidad ejecutada y cuánto se aparta el consumo de materiales del presupuesto.

El jefe de obra mira tres granos distintos. No se aplastan en una sola tabla: la semana de la partida, el día de la cuadrilla y la semana del material no son la misma fila. Sumarlos a la fuerza duplicaría HH o toneladas.

---

## 2. Preguntas que el modelo tiene que poder contestar

1. A la semana de corte, ¿cuánto del contrato está ejecutado y cómo se compara con lo programado?
2. ¿Qué capítulo o partida explica el atraso?
3. En una partida, ¿cuántas HH se van por unidad, y qué cuadrilla se aparta del resto?
4. ¿En qué material, familia o proveedor el consumo se aparta del presupuesto de la semana?

Cada página del dashboard (sección 11) se queda con un subconjunto. Ninguna página lee bronze ni `q_<tabla>`.

---

## 3. Convenciones

| Regla | Definición |
|---|---|
| Zona horaria | `America/Santiago`. La fecha de un hecho es el día civil en Santiago. |
| Semana | Semana ISO. `semana_lunes` es el lunes de esa semana. |
| Fecha | `DATE`. Este modelo no usa `TIMESTAMP`: el parte es un día y el programa es un lunes. El cambio de hora no mueve una fila al día anterior. |
| Montos | CLP, valorizados al precio de contrato. El precio de factura no entra. |
| Porcentajes | `SUM` del numerador / `SUM` del denominador, los dos al grano que se está mirando. |
| Promedio de porcentajes | Prohibido. Un 10% sobre 20 m³ no pesa lo mismo que un 10% sobre 2.000 m³. |
| Unidades distintas | Prohibido sumar cantidades de distinta `unidad_medida`. El rollup entre partidas o materiales usa montos. |
| Denominador 0 | El KPI queda nulo. No es 0%. |
| PII | No hay RUT, nombre de persona, mail, teléfono ni dirección particular. La cuadrilla es un rol (`Cuadrilla pavimento 1`), no una dotación con nombres. |
| Idioma de códigos | snake_case sin tildes (`movimiento_tierras`, `fk_huerfana`). El nombre visible vive en la dimensión. |
| Ids | Se guardan en mayúsculas, con `TRIM`. |
| Catálogos | Se guardan en minúsculas, sin tilde. |

**Regla: los porcentajes se calculan como SUM/SUM, nunca como promedio de porcentajes.**

---

## 4. De dónde salen los datos

En el relato del lab, el residente exporta cinco familias desde el ERP de la obra. El nombre que usa ese relato es SAP: presupuesto de partidas, programa semanal, libro de avance, parte diario de HH y bodega. Sirve para explicar el grano. No es una integración.

No hay host, usuario, RFC, IDoc, OData ni credencial. El paso de datos escribe CSV sintéticos con esta forma. Nadie apunta este repo a un SAP real.

| Extracto del relato | Tabla bronze | Qué decide |
|---|---|---|
| Ficha de la obra | `obras` | Vigencia y mandante |
| Itemizado | `partidas` | Unidad, cantidad de contrato, precio, HH teórica |
| Dotación de terreno | `cuadrillas` | Quién ejecuta, como rol |
| Maestro de insumos | `materiales`, `proveedores` | Unidad, precio de presupuesto, proveedor titular |
| Programa de obra | `programa_avance` | Cantidad programada de la semana |
| Medición de terreno | `medicion_avance` | Cantidad ejecutada de la semana |
| Libro de obra | `parte_hh` | HH y cantidad del día |
| Presupuesto de bodega | `presupuesto_material` | Cantidad presupuestada de la semana |
| Vale de salida, ya resumido a la semana | `vale_consumo` | Cantidad consumida de la semana |

El vale real sería diario. El extracto de este lab ya viene plegado a la semana, porque ese es el grano del hecho. No se modela el vale línea a línea.

Los nombres de obras, mandantes, cuadrillas y proveedores serán ficticios, del tipo «Reposición calzada Los Batros» o «Cuadrilla pavimento 1», en comunas del Gran Concepción (San Pedro de la Paz, Concepción, Chiguayante, Coronel, Hualpén, Talcahuano). No son contratos de la marca.

---

## 5. Bronze

Dataset previsto: `csa_bronze`. Location `US`. Expiración 60 días.

**Todo STRING NULLABLE.** El load no tipa. Lección del incidente de Meli: el DDL de bronze declaraba `activo` BOOL y fechas DATE/TIMESTAMP; con `max_bad_records = 0` el job abortó en `NO-CAST` y la fila nunca llegó a la cuarentena. Subir `max_bad_records` habría perdido la fila en silencio. Aquí el landing acepta el texto. Silver decide con `SAFE_CAST`.

El load del paso siguiente usa schema explícito STRING, `autodetect` apagado, `skip_leading_rows = 1`, `max_bad_records = 0` y `WRITE_TRUNCATE`. Sin streaming.

CSV: UTF-8, separador coma, decimal con punto, fecha `YYYY-MM-DD`, encabezado, campo vacío = NULL. Un decimal con coma va entre comillas (`"12,5"`) y es suciedad de cast, no un separador de columna.

Cada tabla de abajo es una fila con la clave que se indica. El DDL está en [`sql/bronze/ddl.sql`](../sql/bronze/ddl.sql): todo STRING NULLABLE. El Paso 2 lo carga desde CSV.

### 5.1 `obras`

| | |
|---|---|
| Grano | 1 fila = 1 obra |
| Clave | `obra_id` (PK) |

| Columna | Obligatoria | Nota |
|---|---|---|
| `obra_id` | sí | PK |
| `obra_nombre` | sí | |
| `comuna` | sí | Atributo. No hay `d_comuna` |
| `mandante` | sí | Cliente ficticio |
| `tipo_obra` | sí | `pavimentacion`, `conservacion`, `puente`, `aguas_lluvia` |
| `estado_obra` | sí | `en_ejecucion`, `paralizada`, `terminada` |
| `fecha_inicio` | sí | |
| `fecha_termino` | sí | |
| `activo` | sí | `true` / `True` / `1` y `false` / `False` / `0` |

El monto del contrato de la obra es la suma de los montos de sus partidas. No se guarda un segundo total en `obras`: se descuadraría y no cabe en los cinco motivos de cuarentena.

### 5.2 `partidas`

| | |
|---|---|
| Grano | 1 fila = 1 partida de una obra |
| Clave | `partida_id` (PK) |
| FKs | `obra_id` → obras |

| Columna | Obligatoria | Nota |
|---|---|---|
| `partida_id` | sí | PK |
| `obra_id` | sí | |
| `codigo_partida` | sí | Visible, por ejemplo `2.03` |
| `partida_nombre` | sí | |
| `capitulo` | sí | `movimiento_tierras`, `pavimentos`, `obras_arte`, `senalizacion`, `drenaje` |
| `unidad_medida` | sí | `m3`, `m2`, `ml`, `kg`, `ton`, `l`, `un` |
| `cantidad_contrato` | sí | |
| `precio_unitario` | sí | CLP por unidad, precio de contrato |
| `hh_teorica_por_unidad` | no | HH del APU. Vacía es válido: la referencia del gráfico no se dibuja |

`monto_contrato` de la partida se calcula en silver: `cantidad_contrato * precio_unitario`. No viaja en el CSV.

### 5.3 `cuadrillas`

| | |
|---|---|
| Grano | 1 fila = 1 cuadrilla |
| Clave | `cuadrilla_id` (PK) |
| FKs | `obra_id` → obras |

Columnas: `cuadrilla_id`, `cuadrilla_nombre`, `especialidad` (`tierras`, `pavimento`, `estructuras`, `senalizacion`), `obra_id`, `activo`. Todas obligatorias.

En este lab la cuadrilla pertenece a una obra. Moverla de obra sería otro grano.

### 5.4 `proveedores`

| | |
|---|---|
| Grano | 1 fila = 1 proveedor |
| Clave | `proveedor_id` (PK) |

Columnas: `proveedor_id`, `proveedor_nombre`, `rubro` (`cemento`, `arido`, `asfalto`, `acero`, `combustible`), `comuna`, `activo`. Todas obligatorias. Nombres ficticios.

### 5.5 `materiales`

| | |
|---|---|
| Grano | 1 fila = 1 material |
| Clave | `material_id` (PK) |
| FKs | `proveedor_id` → proveedores |

Columnas: `material_id`, `material_nombre`, `familia` (el mismo catálogo que `rubro`), `unidad_medida`, `precio_unitario`, `proveedor_id`. Todas obligatorias.

`precio_unitario` es el precio de presupuesto. El hecho de consumo valoriza con ese precio los dos lados, así la desviación mide cantidad. La variación de precio de la factura queda fuera.

Un material tiene un proveedor titular. Partir el consumo entre dos proveedores cambiaría el grano de `f_consumo_material`. Este paso no lo hace.

### 5.6 `programa_avance`

| | |
|---|---|
| Grano | 1 fila = 1 partida programada en una semana |
| Clave | `programa_id` (PK). Llave natural (`obra_id`, `partida_id`, `semana_lunes`) |
| FKs | `obra_id` → obras; `partida_id` → partidas |

Columnas, todas obligatorias: `programa_id`, `obra_id`, `partida_id`, `semana_lunes`, `cantidad_programada`.

### 5.7 `medicion_avance`

| | |
|---|---|
| Grano | 1 fila = 1 medición de una partida en una semana |
| Clave | `medicion_id` (PK). Llave natural (`obra_id`, `partida_id`, `semana_lunes`) |
| FKs | `obra_id` → obras; `partida_id` → partidas |

Columnas, todas obligatorias: `medicion_id`, `obra_id`, `partida_id`, `semana_lunes`, `cantidad_ejecutada`.

### 5.8 `parte_hh`

| | |
|---|---|
| Grano | 1 fila = 1 parte diario de una cuadrilla en una obra |
| Clave | `parte_id` (PK). Llave natural (`obra_id`, `cuadrilla_id`, `fecha`) |
| FKs | `obra_id` → obras; `cuadrilla_id` → cuadrillas; `partida_id` → partidas |

Columnas, todas obligatorias: `parte_id`, `obra_id`, `cuadrilla_id`, `partida_id`, `fecha`, `hh`, `cantidad_ejecutada`.

El grano pedido del hecho es obra × cuadrilla × día. `partida_id` va en la fila como atributo: ese día la cuadrilla se imputa a una sola partida. Si el día real se parte en dos partidas, harían falta dos filas y la llave natural pasaría a incluir la partida. Este modelo no representa ese caso.

`hh = 0` y `cantidad_ejecutada = 0` son un día sin producción. El campo vacío no es cero: es nulo obligatorio.

### 5.9 `presupuesto_material`

| | |
|---|---|
| Grano | 1 fila = 1 material presupuestado en una obra y una semana |
| Clave | `presupuesto_id` (PK). Llave natural (`obra_id`, `material_id`, `semana_lunes`) |
| FKs | `obra_id` → obras; `material_id` → materiales |

Columnas, todas obligatorias: `presupuesto_id`, `obra_id`, `material_id`, `semana_lunes`, `cantidad_presupuestada`.

### 5.10 `vale_consumo`

| | |
|---|---|
| Grano | 1 fila = 1 consumo semanal de un material en una obra |
| Clave | `vale_id` (PK). Llave natural (`obra_id`, `material_id`, `semana_lunes`) |
| FKs | `obra_id` → obras; `material_id` → materiales |

Columnas, todas obligatorias: `vale_id`, `obra_id`, `material_id`, `semana_lunes`, `cantidad_real`.

### 5.11 Catálogos cerrados

Un código fuera de su lista, con texto no vacío, cae en `cast_fallido`: el dominio se trata como un cast. `SAFE_CAST` al código devuelve NULL y el texto original sigue en la cuarentena.

| Campo | Códigos |
|---|---|
| `tipo_obra` | `pavimentacion`, `conservacion`, `puente`, `aguas_lluvia` |
| `estado_obra` | `en_ejecucion`, `paralizada`, `terminada` |
| `capitulo` | `movimiento_tierras`, `pavimentos`, `obras_arte`, `senalizacion`, `drenaje` |
| `especialidad` | `tierras`, `pavimento`, `estructuras`, `senalizacion` |
| `familia`, `rubro` | `cemento`, `arido`, `asfalto`, `acero`, `combustible` |
| `unidad_medida` | `m3`, `m2`, `ml`, `kg`, `ton`, `l`, `un` |

Nombre visible de la unidad, en la dimensión: `m3` → m³, `m2` → m², `ml` → ml, `kg` → kg, `ton` → t, `l` → L, `un` → un.

---

## 6. Silver y cuarentena

Dataset previsto: `csa_silver`. Expiración 60 días. Entrada: `csa_bronze`, todo STRING NULLABLE. Salida: una tabla tipada por entidad y `q_<tabla>` con la fila cruda, un motivo y la regla (el campo que disparó).

El SQL vive en `sql/silver/`. En cada archivo, dos `CREATE OR REPLACE`: la tabla limpia y `q_<tabla>`. Sin DML.

Ninguna fila de bronze desaparece: o queda en silver o queda en `q_<tabla>`.

```text
filas(bronze T) = filas(silver T) + filas(q_T)
```

Orden de build, porque la FK se valida contra la dimensión **silver**. Un padre en cuarentena no alcanza para dar por buena a la hija:

1. `obras`
2. `proveedores`
3. `partidas`
4. `cuadrillas`
5. `materiales`
6. `programa_avance`
7. `medicion_avance`
8. `parte_hh`
9. `presupuesto_material`
10. `vale_consumo`

En cada fila:

- `TRIM` del texto. Ids a mayúsculas. Catálogos a minúsculas.
- Fechas con `SAFE_CAST` a `DATE`. Cantidades, HH y precios con `SAFE_CAST` a `NUMERIC`. `activo` con la lista de la sección 5.1.
- Campo vacío después del `TRIM` es NULL. Un opcional vacío (`hh_teorica_por_unidad`) sigue en silver. Si el opcional trae texto y el cast falla, el motivo es `cast_fallido`: la fila no se parte.
- Dedup con `QUALIFY ROW_NUMBER()` sobre la llave natural, solo entre filas que ya pasaron cast y nulos. Se queda la de menor id. La copia va a cuarentena. Las dos copias no se suman.
- FK con valor que no está en la dimensión silver es huérfana. En este modelo no hay FK opcional.
- La FK de partida, en programa, medición y parte, exige además que `partidas.obra_id` sea el `obra_id` de la fila. La FK de cuadrilla en el parte exige que `cuadrillas.obra_id` sea el de la fila. Si el id existe y pertenece a otra obra, el motivo es `fk_huerfana`.

### Prioridad de motivos

Una fila con varios problemas sale **una vez**, con el primer motivo de esta lista:

```text
cast_fallido > nulo_obligatorio > duplicado > fk_huerfana > fecha_incoherente
```

| Orden | Motivo | Cuándo |
|---|---|---|
| 1 | `cast_fallido` | Hay texto y `SAFE_CAST` devuelve NULL, o el código no está en el catálogo |
| 2 | `nulo_obligatorio` | Falta la PK, una FK obligatoria, una fecha requerida o una medida requerida |
| 3 | `duplicado` | `ROW_NUMBER > 1` de la llave natural, entre las que pasaron 1 y 2 |
| 4 | `fk_huerfana` | El valor no está en la dimensión silver |
| 5 | `fecha_incoherente` | La fecha parseó, y no calza con la regla de la sección 7 |

El cast va primero: si `cantidad_programada = NO-CAST` y además la PK viene vacía, el motivo es `cast_fallido`. No se parte la fila en dos cuarentenas. Si no, la igualdad bronze = silver + cuarentena no cierra.

El duplicado se evalúa antes que la FK. La copia de una fila válida es `duplicado`. La copia de una fila rota ni siquiera entra al `ROW_NUMBER`: ya salió por cast o por nulo.

`fecha_incoherente` solo se mira en filas que pasaron los cuatro motivos anteriores. Si la obra padre está en cuarentena, la hija sale por `fk_huerfana`.

La cuarentena no entra al numerador ni al denominador de ningún KPI.

---

## 7. Suciedad planeada

Cada motivo se planta como **filas extra**. El núcleo limpio no se muta. Los conteos, por tabla y por motivo ganador, están en [`data/manifest.json`](../data/manifest.json) y en [paso-02-bronze.md](paso-02-bronze.md).

Cada fila plantada trae un solo problema, para que el motivo se pueda ver. Además se planta al menos una fila con cast roto y PK vacía a la vez: el motivo tiene que ser `cast_fallido`.

| Motivo | Cómo se ve | Dónde aplica |
|---|---|---|
| `cast_fallido` | `NO-CAST` en cantidad, HH, precio o fecha; fecha `2026-02-31`; decimal entre comillas `"12,5"`; `activo = SI`; código fuera de catálogo | Toda tabla con un campo tipado o un catálogo |
| `nulo_obligatorio` | PK vacía, FK vacía, `semana_lunes` o `fecha` vacía, medida requerida vacía | Todas |
| `duplicado` | Segunda copia de la llave natural | Todas |
| `fk_huerfana` | `OBR-HUERFANA`, `PAR-HUERFANA`, `CUA-HUERFANA`, `MAT-HUERFANA`, `PRV-HUERFANO`. También una partida o cuadrilla que existe y pertenece a otra obra | Toda tabla con FK. `obras` y `proveedores` no tienen padre |
| `fecha_incoherente` | Ver abajo | `obras`, `programa_avance`, `medicion_avance`, `parte_hh`, `presupuesto_material`, `vale_consumo` |

`fecha_incoherente`, con FK válida y cast bueno, para que gane este motivo:

- En `obras`: `fecha_termino` anterior a `fecha_inicio`.
- En programa, medición, presupuesto y vale: `semana_lunes` que no es lunes. Ejemplo que sí parsea: `2026-05-06` cae miércoles. También una semana anterior a `fecha_inicio` o posterior a `fecha_termino` de la obra silver.
- En `parte_hh`: `fecha` fuera de `[fecha_inicio, fecha_termino]` de la obra silver.

Un lunes válido de ejemplo, para no confundirlo con la suciedad: `2026-05-04`.

Cantidad negativa, HH negativa o precio menor o igual a cero no están en la suciedad planeada. El cast de un `-3` funciona, así que no se disfraza de `cast_fallido`. El generador no los emite. Un sexto motivo queda fuera de este paso.

Los centinelas `OBR-HUERFANA`, `PAR-HUERFANA`, `CUA-HUERFANA`, `MAT-HUERFANA` y `PRV-HUERFANO` no se cargan como filas maestras.

---

## 8. Estrella gold

Dataset previsto: `csa_gold`. Expiración 60 días. El SQL vive en `sql/gold/`. Cada tabla es `CREATE OR REPLACE … AS SELECT` desde silver. Sin DML. Sin lectura de bronze ni de `q_<tabla>`.

Tres hechos, porque los granos no coinciden. `f_consumo_material` se justifica: el cemento de la semana alimenta varias partidas y este lab no trae la dosificación que lo prorratearía. Meterlo en `f_avance_partida` repetiría la tonelada o la dejaría fuera. Meterlo en `f_hh_cuadrilla` partiría la bodega por día de cuadrilla sin un vale que lo diga. El grano obra × material × semana es el único donde la desviación suma sin doble conteo.

```text
                         d_fecha
                            |
d_cuadrilla —— f_hh_cuadrilla —— d_obra —— f_avance_partida —— d_partida
                            |                  |
                       d_partida               |
                                               |
              d_proveedor —— d_material —— f_consumo_material
```

`d_partida` se une al avance y al parte. `d_material` y `d_proveedor` se unen al consumo. `d_obra` y `d_fecha` se comparten.

### Por qué gold no parte por fecha

En el sandbox la partición expira a los 60 días según su fecha. Una obra de varios meses perdería las semanas viejas y la curva acumulada se cortaría sola. Por eso gold **no usa partición por fecha**. Usa `CLUSTER BY`. La tabla entera vive 60 días desde que `make run` la vuelve a crear.

| Tabla | Cluster |
|---|---|
| `f_avance_partida` | `CLUSTER BY obra_id, partida_id` |
| `f_hh_cuadrilla` | `CLUSTER BY obra_id, cuadrilla_id` |
| `f_consumo_material` | `CLUSTER BY obra_id, material_id` |
| `d_obra` | `CLUSTER BY obra_id` |
| `d_partida` | `CLUSTER BY obra_id, partida_id` |
| `d_cuadrilla` | `CLUSTER BY obra_id, cuadrilla_id` |
| `d_material` | `CLUSTER BY material_id, proveedor_id` |
| `d_proveedor` | `CLUSTER BY proveedor_id` |
| `d_fecha` | `CLUSTER BY fecha` |

### 8.1 `f_avance_partida`

| | |
|---|---|
| Grano | **obra × partida × semana** (1 fila = 1 obra × 1 partida × 1 semana) |
| Clave | (`obra_id`, `partida_id`, `semana_lunes`) |
| Cluster | `CLUSTER BY obra_id, partida_id` |

Sale del full outer entre `programa_avance` y `medicion_avance` silver, en esa llave. El precio sale de `d_partida`.

| Columna | Tipo | Significado |
|---|---|---|
| `obra_id` | STRING | |
| `partida_id` | STRING | |
| `semana_lunes` | DATE | Lunes de la semana |
| `cantidad_programada` | NUMERIC | 0 si esa semana solo tiene medición |
| `cantidad_ejecutada` | NUMERIC | 0 si esa semana solo tiene programa |
| `precio_unitario` | NUMERIC | Precio de contrato de la partida |
| `monto_programado` | NUMERIC | `cantidad_programada * precio_unitario` |
| `monto_ejecutado` | NUMERIC | `cantidad_ejecutada * precio_unitario` |

El cero conserva el lado que sí existe dentro del `SUM`. NULL en el lado que falta sacaría esa semana del programa y el SPI se vería mejor de lo que está. Una fila en cuarentena no se reemplaza por cero: no llegó a silver, y el hecho no la inventa.

Una semana que no está en ninguno de los dos silver no existe en el hecho. El eje continuo de la curva S, con lunes en cero, puede armarse en el paso gold contra `d_fecha`. El hecho no guarda esas semanas vacías.

No se guarda el porcentaje ni el SPI en la fila. Guardarlos invitaría a promediarlos.

La partida puede ejecutar más que el contrato. El % puede pasar de 100%. No se capa.

### 8.2 `f_hh_cuadrilla`

| | |
|---|---|
| Grano | **1 fila = 1 obra × 1 cuadrilla × 1 día** |
| Clave | (`obra_id`, `cuadrilla_id`, `fecha`) |
| Cluster | `CLUSTER BY obra_id, cuadrilla_id` |

Sale de `parte_hh` silver. `partida_id` es atributo de ese día.

| Columna | Tipo | Significado |
|---|---|---|
| `obra_id` | STRING | |
| `cuadrilla_id` | STRING | |
| `partida_id` | STRING | La partida de ese día |
| `fecha` | DATE | |
| `hh` | NUMERIC | Horas hombre del día |
| `cantidad_ejecutada` | NUMERIC | En la unidad de la partida |

No se guarda `hh / cantidad_ejecutada`. El rendimiento de la fila, promediado, es el error que este modelo evita.

### 8.3 `f_consumo_material`

| | |
|---|---|
| Grano | **1 fila = 1 obra × 1 material × 1 semana** |
| Clave | (`obra_id`, `material_id`, `semana_lunes`) |
| Cluster | `CLUSTER BY obra_id, material_id` |

Full outer entre `presupuesto_material` y `vale_consumo` silver. El precio sale de `d_material`.

| Columna | Tipo | Significado |
|---|---|---|
| `obra_id` | STRING | |
| `material_id` | STRING | |
| `semana_lunes` | DATE | |
| `cantidad_presupuestada` | NUMERIC | 0 si esa semana solo tiene vale |
| `cantidad_real` | NUMERIC | 0 si esa semana solo tiene presupuesto |
| `precio_unitario` | NUMERIC | Precio de presupuesto del material |
| `monto_presupuestado` | NUMERIC | `cantidad_presupuestada * precio_unitario` |
| `monto_real` | NUMERIC | `cantidad_real * precio_unitario` |

Misma regla del cero que en el avance. Misma prohibición de guardar la desviación en la fila.

### 8.4 Dimensiones

| Dim | Grano | Clave | Atributos que el dashboard muestra |
|---|---|---|---|
| `d_obra` | 1 obra | `obra_id` | nombre, comuna, mandante, `tipo_obra`, `estado_obra`, `fecha_inicio`, `fecha_termino`, `activo` |
| `d_partida` | 1 partida | `partida_id` | `obra_id`, código, nombre, `capitulo`, `unidad_medida`, nombre de la unidad, `cantidad_contrato`, `precio_unitario`, `monto_contrato`, `hh_teorica_por_unidad` |
| `d_cuadrilla` | 1 cuadrilla | `cuadrilla_id` | nombre, `especialidad`, `obra_id`, `activo` |
| `d_material` | 1 material | `material_id` | nombre, `familia`, `unidad_medida`, nombre de la unidad, `precio_unitario`, `proveedor_id` |
| `d_proveedor` | 1 proveedor | `proveedor_id` | nombre, `rubro`, comuna, `activo` |
| `d_fecha` | 1 día | `fecha` | `anio`, `mes`, `mes_nombre`, `semana_iso`, `lunes_semana`, `nombre_dia`, `es_fin_de_semana` |

`monto_contrato` en `d_partida` es `cantidad_contrato * precio_unitario`, una vez por partida. El % de avance físico usa esa suma. Si alguien copia `monto_contrato` en cada semana del hecho y lo vuelve a sumar, una partida de 20 semanas infla el denominador veinte veces.

`d_fecha` se construye en gold (`GENERATE_DATE_ARRAY` dentro del `CREATE OR REPLACE`), desde el `fecha_inicio` más temprano hasta el `fecha_termino` más tardío de las obras silver. No es un extracto bronze. `es_fin_de_semana` marca sábado y domingo. Los feriados quedan fuera de este paso.

Uniones de `d_fecha`:

- `f_avance_partida.semana_lunes = d_fecha.fecha`
- `f_consumo_material.semana_lunes = d_fecha.fecha`
- `f_hh_cuadrilla.fecha = d_fecha.fecha`

Es la misma tabla. En Looker son dos roles (semana y día), no dos calendarios.

---

## 9. Métricas

Todas se leen desde el hecho que corresponde, o desde un agregado que guarde **sumas**. El porcentaje se cierra al final del filtro.

Ventana por defecto, para que las cuatro tarjetas no contesten preguntas distintas con el mismo título:

- `% avance físico` y SPI: acumulado desde la primera semana de la obra hasta la semana de corte, inclusive. Las dos sumas usan esa misma ventana.
- HH por unidad y desviación de consumo: el período que el jefe filtró (la semana o el mes que está mirando).

### 9.1 % avance físico

```text
% avance físico = SUM(monto_ejecutado) / SUM(monto_contrato)
```

`SUM(monto_ejecutado)` sale de `f_avance_partida`, acumulado al corte. `SUM(monto_contrato)` sale de `d_partida`, una vez por partida del filtro (obra, capítulo, partida). No sale de una columna repetida en cada semana.

Si `SUM(monto_contrato) = 0`, el KPI es nulo.

El precio es el de contrato. El indicador compara cantidades valorizadas. No es un estado de pago.

### 9.2 SPI

SPI = avance real / programado, cerrado como SUM/SUM:

```text
SPI = SUM(monto_ejecutado) / SUM(monto_programado)
```

Las dos sumas salen de `f_avance_partida`, en la misma ventana. SPI 1 es ir al día con el programa. Sobre 1, hay más ejecución que programa. Bajo 1, hay menos.

Si `SUM(monto_programado) = 0`, el KPI es nulo. Una semana ejecutada sin programa suma al numerador y no al denominador: el SPI del acumulado sube, y esa semana se ve.

El SPI de la tarjeta no es el promedio de los SPI semanales. Cada punto de una serie semanal vuelve a calcular `SUM / SUM` dentro de su semana.

### 9.3 HH por unidad ejecutada

```text
HH por unidad ejecutada = SUM(hh) / SUM(cantidad_ejecutada)
```

Las dos sumas salen de `f_hh_cuadrilla`. El resultado se lee en la unidad de la partida (HH/m³, HH/ml).

El KPI exige una sola `unidad_medida` en el filtro. Si el filtro mezcla unidades, el KPI es nulo. La página lo muestra por partida, o con una partida elegida. `hh_teorica_por_unidad` es una constante de `d_partida`, la referencia del gráfico. No es un promedio de rendimientos diarios.

Si `SUM(cantidad_ejecutada) = 0`, el KPI es nulo.

### 9.4 Desviación de consumo de materiales

```text
desviación de consumo = (SUM(monto_real) - SUM(monto_presupuestado)) / SUM(monto_presupuestado)
```

Las sumas salen de `f_consumo_material`. Positivo: se consumió más que el presupuesto, a precio de presupuesto. Cero: calza. Negativo: se consumió menos.

Dentro de un solo material la misma forma con cantidades da el mismo número, porque el precio es el de `d_material` en los dos lados y se cancela. Entre materiales solo vale la forma en montos. Sumar kg de cemento con litros de combustible está prohibido.

Si `SUM(monto_presupuestado) = 0`, el KPI es nulo. Un vale sin presupuesto no se muestra como desviación 0%.

### 9.5 Qué rompe el número

| Antipatrón | Qué le hace al KPI |
|---|---|
| `AVG(pct_avance)` o `AVG(spi)` por partida, semana o cuadrilla | Promedio de porcentajes. La partida chica pesa igual que la grande. |
| Promediar los SPI de cada semana para «el SPI del mes» | Segundo promedio. El mes es `SUM` del mes / `SUM` del mes. |
| `AVG(hh / cantidad_ejecutada)` | Promedio de rendimientos diarios. Un día de 2 m³ pesa igual que un día de 200 m³. |
| `AVG(desviacion_fila)` | La misma trampa, en materiales. |
| `SUM(monto_contrato)` copiado en cada semana del hecho | El denominador del % avance crece con las semanas. |
| `SUM(cantidad_ejecutada)` de partidas con distinta unidad | Suma m³ con ml. El KPI de HH tiene que salir nulo. |
| Contar filas de `q_<tabla>` dentro del KPI | Mete a la cuarentena en el porcentaje «para no perder datos». |
| Denominador 0 mostrado como 0% | Una partida sin programa parece perfecta. |

---

## 10. Agregado permitido

Si una vista existe para no escanear el hecho, guarda aditivos. El porcentaje se calcula en el gráfico.

Avance, por `semana_lunes`, `obra_id`, `partida_id` (y los atributos de corte: capítulo): `SUM(monto_programado)`, `SUM(monto_ejecutado)`, `SUM(cantidad_programada)`, `SUM(cantidad_ejecutada)`. El `monto_contrato` sigue en `d_partida`, una fila por partida.

HH, por `fecha` o `lunes_semana`, `obra_id`, `cuadrilla_id`, `partida_id`: `SUM(hh)`, `SUM(cantidad_ejecutada)`.

Consumo, por `semana_lunes`, `obra_id`, `material_id`: `SUM(monto_real)`, `SUM(monto_presupuestado)`, `SUM(cantidad_real)`, `SUM(cantidad_presupuestada)`.

Guardar el porcentaje ya cerrado en la vista queda solo como columna de auditoría, nunca como métrica de Looker.

---

## 11. Páginas del dashboard futuro

Borrador. Se afina en el paso gold. La guía visual está en [`looker/STYLE_GUIDE.md`](../looker/STYLE_GUIDE.md). Cada página consume solo gold.

| Página | Pregunta | Métrica | Cortes |
|---|---|---|---|
| **Avance vs programa** | ¿Vamos al día con el programa y cuánto del contrato ya está hecho? | `% avance físico = SUM(monto_ejecutado) / SUM(monto_contrato)` y `SPI = SUM(monto_ejecutado) / SUM(monto_programado)`, más las dos sumas de la curva | Obra, capítulo, partida, semana de corte |
| **Productividad HH** | ¿Cuántas HH se van por unidad y qué cuadrilla se aparta, en la misma partida? | `HH por unidad ejecutada = SUM(hh) / SUM(cantidad_ejecutada)`, contra `hh_teorica_por_unidad` | Obra, partida, cuadrilla, semana |
| **Materiales** | ¿Dónde el consumo se aparta del presupuesto? | `desviación de consumo = (SUM(monto_real) - SUM(monto_presupuestado)) / SUM(monto_presupuestado)` | Obra, familia, material, proveedor, semana |

La curva de avance es la suma acumulada de `monto_programado` y de `monto_ejecutado`. No es un promedio de porcentajes semanales.

Lo que estas páginas no contestan, a propósito:

- Estado de pago, reajuste y precio de factura.
- Dotación con nombre, asistencia por persona, accidente.
- Dosificación de un material entre varias partidas.
- GPS de maquinaria.

---

## 12. Sandbox

El proyecto corre, cuando se cree, en **BigQuery sandbox, sin facturación**. Eso fija el diseño:

| Permitido | No entra |
|---|---|
| Load job `WRITE_TRUNCATE` | `INSERT` / `UPDATE` / `DELETE` / `MERGE` |
| `CREATE OR REPLACE` de tablas y vistas | Streaming inserts |
| Expiración de tablas a 60 días | Una expiración más larga |
| `CLUSTER BY` en gold | Partición por fecha en gold |

No hay `ALTER`. Si el shape cambia, `CREATE OR REPLACE` deja el objeto nuevo y el load, en bronze, lo vuelve a llenar. A los 60 días el sandbox borra las tablas. `make run` las reconstruye desde cero. No hay estado que migrar.

Location `US`: es el sandbox de este lab. Los datos son sintéticos y no hay requisito de dejarlos en Chile. La fecha de negocio sigue siendo `America/Santiago`.

Auth: Application Default Credentials, en la Mac de Julio. `GCP_PROJECT` es obligatorio. No hay proyecto por defecto en el código. El nombre previsto es `csa-obra-jp`; este paso no lo crea y el repo no lo deja escrito como fallback. No hay llave de service account en el repo ni en la VM del agente.

`DRY=1` no llama a BigQuery. En CI, `DRY` parte en 1. `DRY=1` no reemplaza la lección del load: en Meli el dry-run miraba el header y no el valor contra el tipo. Por eso bronze queda todo STRING NULLABLE antes de que exista el primer CSV.

---

## 13. Qué queda fuera

El Paso 2 ya escribió el generador, el manifest y el DDL bronze. Siguen fuera:

- El SQL de `sql/silver/` y `sql/gold/`.
- El informe de Looker Studio publicado.
- Logos o piezas gráficas de la marca.
- Cualquier conexión real al ERP.

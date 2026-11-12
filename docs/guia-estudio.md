# Guía de estudio — entrevista BI (caso CSA / BigQuery)

**Para:** Julio Pradenas  
**Repo:** [JulioPradenas/csa-obra-bq](https://github.com/JulioPradenas/csa-obra-bq)  
**Uso:** preparar la defensa oral del portafolio (BI, modelo, calidad de datos, sandbox).  
**Alcance:** lab de portafolio. Marca con fines ilustrativos, obra vial ambientada en el Biobío. **No** atribuir contratos, rendimientos ni datos a Ingeniería CSA ni a ningún empleador.

Números de abajo salen de la corrida real de Julio (seed 42), de `data/manifest.json`, `docs/paso-02-bronze.md`, `docs/paso-03-silver.md`, `docs/paso-04-gold.md` y `looker/STYLE_GUIDE.md`. **No inventar.**

---

## 1) El proyecto en 2 minutos (pitch hablado)

> “Es un lab de obra vial: el programa, el parte diario y la bodega viven en exports distintos, y el porcentaje de avance se promedia mal. Armé un ELT en BigQuery sandbox (`GCP_PROJECT=csa-obra-jp`, location US): CSV sintéticos seed 42, siete obras en comunas reales del Biobío, bronze todo STRING, silver con cuarentena y gold en estrella. Hay tres granos, porque no coinciden: avance es obra × partida × semana, HH es obra × cuadrilla × día, materiales es obra × material × semana. Los porcentajes son SUM/SUM sobre montos, nunca un promedio de porcentajes. Gold no parte por fecha: en el sandbox la partición vence a los 60 días según esa fecha y se comería la curva de mayo a noviembre; uso `CLUSTER BY obra_id` y la segunda clave del hecho. Sin filtro, bronze tiene 4.819 filas, silver 4.771 y la cuarentena 48. El SPI global es 0,90, pero Hualpén está en 0,55 y Los Batros en 0,70. El asfalto de Coronel se desvía 0,40. Auth solo con ADC. El dashboard en Data Studio lo estoy armando yo; todavía no hay link público.”

Si preguntan “¿es producción?”: *lab operable de punta a punta con datos sintéticos. El contrato de grano y de métricas es el que engancharías a un export del libro de obra.*

---

## 2) Recorrido paso a paso (1–4)

| Paso | Qué | Por qué | Cómo / artefactos | PR |
|---|---|---|---|---|
| **1** | Esqueleto, modelo y guía visual | Fijar grano, fórmulas y páginas antes de generar datos | [`docs/modelo-datos.md`](modelo-datos.md), [`looker/STYLE_GUIDE.md`](../looker/STYLE_GUIDE.md) | [#1](https://github.com/JulioPradenas/csa-obra-bq/pull/1) |
| **2** | CSV + manifest + bronze | Contrato reproducible y landing que acepta basura | [`scripts/generar_datos.py`](../scripts/generar_datos.py), [`data/manifest.json`](../data/manifest.json), [`sql/bronze/ddl.sql`](../sql/bronze/ddl.sql), [`docs/paso-02-bronze.md`](paso-02-bronze.md). Seed **42** | [#2](https://github.com/JulioPradenas/csa-obra-bq/pull/2) |
| **3** | Silver + cuarentena | Tipar y deduplicar sin perder filas | [`sql/silver/`](../sql/silver/), [`scripts/motivos.py`](../scripts/motivos.py), [`docs/paso-03-silver.md`](paso-03-silver.md). Prioridad de un motivo por fila | [#3](https://github.com/JulioPradenas/csa-obra-bq/pull/3) |
| **4** | Gold estrella | El dashboard lee aditivos, no re-define el SPI | [`sql/gold/`](../sql/gold/), [`docs/paso-04-gold.md`](paso-04-gold.md). Sin partición por fecha | [#4](https://github.com/JulioPradenas/csa-obra-bq/pull/4) |

**Entry point:** `make run` = generar CSV → load bronze (`WRITE_TRUNCATE`) → silver → gold → verify. Cada capa es `CREATE OR REPLACE` o un load job. Auth: `gcloud auth application-default login` y `export GCP_PROJECT=csa-obra-jp`. No hay default de proyecto en el código.

El dashboard queda **pendiente**. El plan de páginas y los valores sin filtro están en la guía de estilo; no hay viewer ni capturas.

---

## 3) Modelo y grano

No hay un solo hecho. El jefe mira tres preguntas con tres granos. Aplastarlos duplicaría HH o toneladas.

| Objeto | 1 fila = | Dónde vive |
|---|---|---|
| `programa_avance` / `medicion_avance` | 1 partida de una obra en una semana | bronze / silver |
| `parte_hh` | 1 cuadrilla de una obra en un día | bronze / silver |
| `presupuesto_material` / `vale_consumo` | 1 material de una obra en una semana | bronze / silver |
| `f_avance_partida` | obra × partida × semana que pasó silver | gold, **735** |
| `f_hh_cuadrilla` | obra × cuadrilla × día | gold, **1.470** |
| `f_consumo_material` | obra × material × semana | gold, **882** |
| `d_obra` | 1 obra | gold, **7** |
| `d_proveedor` | 1 proveedor | gold, **5** |
| `d_partida` | 1 partida | gold, **35** |
| `d_cuadrilla` | 1 cuadrilla | gold, **14** |
| `d_material` | 1 material | gold, **6** |
| `d_fecha` | 1 día (2026-05-04 → 2026-11-27) | gold, **208** |

`f_consumo_material` existe porque el cemento de la semana alimenta varias partidas y este lab no trae la dosificación. Meterlo en el avance repetiría la tonelada. `partida_id` en el parte es atributo: ese día la cuadrilla se imputa a una sola partida.

El monto del contrato vive en `d_partida`, una vez. No se copia en cada semana del hecho.

---

## 4) Generador, seed y la historia

[`scripts/generar_datos.py`](../scripts/generar_datos.py). Seed **42**. El extracto semanal va del lunes **2026-05-04** al **2026-09-21**. La vigencia de las obras llega al **2026-11-27**. No usa `date.today()`, así que dos corridas dan el mismo CSV.

Las anomalías son **filas extra**. El núcleo limpio no se muta. El manifest cuenta el motivo ganador, no cada defecto por separado.

Historia sobre las filas que llegan a silver y a gold, sin filtro. Los montos son la suma, en CLP.

| Corte | Número | Cómo se lee |
|---|---|---|
| SPI global | **0,90** | 4.941.031.200 / 5.503.260.000. La tarjeta a 2 decimales muestra 0,90. El cociente fino es 0,8978 |
| % avance físico global | **0,72** | 4.941.031.200 / 6.879.075.000. El fino es 0,7183. Tarjeta a 1 decimal: 71,8% |
| Los Batros `OBR-01`, San Pedro de la Paz | SPI **0,70**, avance **0,56** | En ejecución y atrás del programa |
| Talcahuano `OBR-02` | SPI **1,05** | Va sobre el programa |
| Hualpén `OBR-06` | SPI **0,55** | Paralizada. El global 0,90 no la muestra |
| Desviación global de materiales | **0,0455** | 2.430.951.600 real contra 2.325.111.600 presupuestado |
| Asfalto Coronel `OBR-05` / `MAT-ASF` | **0,40** | La carpeta es `PAR-05-203`. El vale no se prorratea entre partidas |
| HH/unidad, tierras | Los Batros **1,40** contra Talcahuano **0,80** | `SUM(hh) / SUM(cantidad_ejecutada)` dentro de la cuadrilla |
| `SUM(hh)` | **42.707,7** | Aditivo. Sin filtro de partida el ratio de HH es nulo: hay más de una unidad |

**Lección:** el SPI global 0,90 esconde la dispersión. Hualpén está en 0,55 y Los Batros en 0,70. Un promedio de los SPI por obra pesaría igual una obra chica que una grande. El 0,90 sale de sumar los montos y dividir al final.

Nombres de obras, mandantes, cuadrillas y proveedores son ficticios. Las comunas son reales.

---

## 5) Bronze todo STRING

Bronze es landing. **Todas** las columnas de [`sql/bronze/ddl.sql`](../sql/bronze/ddl.sql) son `STRING` y NULLABLE. El load es `WRITE_TRUNCATE`, schema explícito STRING, `max_bad_records=0`.

### Por qué, y de dónde sale la lección

En el lab de fulfillment (Meli) el DDL tipaba `activo` como BOOL y las fechas como DATE o TIMESTAMP. BigQuery parsea el CSV contra ese tipo. Con `max_bad_records=0` el job abortó entero en `NO-CAST`. `DRY=1` no lo vio: miraba el header, no el valor contra el tipo.

**Qué no se hace:** subir `max_bad_records`. Eso tira filas en silencio y rompe `bronze = silver + cuarentena`.

**Qué se hizo acá desde el paso 2:** bronze nace todo STRING. Silver castea con `SAFE_CAST`. `activo` acepta `true` / `True` / `1` y `false` / `False` / `0`. `NO-CAST`, `12,5` y `2026-02-31` entran a bronze y salen en cuarentena como `cast_fallido`. El BOOL no se deja al `SAFE_CAST` de BigQuery: el `'1'` del contrato no es el parseo por defecto del motor, así que el SQL lo lista.

### Conteos de la corrida de Julio (seed 42)

| Tabla | Bronze | Silver | Cuarentena |
|---|---:|---:|---:|
| `obras` | 12 | 7 | 5 |
| `proveedores` | 8 | 5 | 3 |
| `partidas` | 39 | 35 | 4 |
| `cuadrillas` | 18 | 14 | 4 |
| `materiales` | 10 | 6 | 4 |
| `programa_avance` | 742 | 735 | 7 |
| `medicion_avance` | 740 | 735 | 5 |
| `parte_hh` | 1.476 | 1.470 | 6 |
| `presupuesto_material` | 887 | 882 | 5 |
| `vale_consumo` | 887 | 882 | 5 |
| **Total** | **4.819** | **4.771** | **48** |

Cada tabla cierra: bronze = silver + cuarentena. `verify_silver` en la corrida real dio OK, **0 huérfanas** en silver, y **44** conteos por motivo distintos de cero, todos OK. Los ceros también calzan; el reporte no los imprime.

---

## 6) Silver: prioridad de motivos

Una fila de bronze termina en la tabla silver **o** en `q_<tabla>`, nunca en las dos y nunca en ninguna. Si tiene varios problemas, sale **una vez**, con el primer motivo de esta lista:

| Orden | Motivo | Cuándo |
|---|---|---|
| 1 | `cast_fallido` | Hay texto y `SAFE_CAST` devuelve NULL, o el código no está en el catálogo |
| 2 | `nulo_obligatorio` | Falta la PK, una FK obligatoria, una fecha requerida o una medida requerida |
| 3 | `duplicado` | `ROW_NUMBER > 1` de la llave natural, entre las que pasaron 1 y 2 |
| 4 | `fk_huerfana` | El valor no está en la dimensión **silver**, o la partida o la cuadrilla es de otra obra |
| 5 | `fecha_incoherente` | El término es anterior al inicio, la semana no cae lunes, o la fecha está fuera de la vigencia |

El cast va primero. Hay una fila de `obras` con `fecha_inicio = NO-CAST` y `obra_id` vacío. El motivo es `cast_fallido`, no los dos. Si no, esa fila contaría dos veces y 4.819 dejaría de ser 4.771 + 48.

La FK se evalúa contra la dimensión silver ya limpia. Un padre en cuarentena no alcanza para dar por bueno al hijo. El orden de los SQL es dimensiones antes que hechos.

| Tabla | cast | nulo | duplicado | fk | fecha |
|---|---:|---:|---:|---:|---:|
| `obras` | 2 | 1 | 1 | 0 | 1 |
| `proveedores` | 1 | 1 | 1 | 0 | 0 |
| `partidas` | 1 | 1 | 1 | 1 | 0 |
| `cuadrillas` | 1 | 1 | 1 | 1 | 0 |
| `materiales` | 1 | 1 | 1 | 1 | 0 |
| `programa_avance` | 1 | 1 | 1 | 2 | 2 |
| `medicion_avance` | 1 | 1 | 1 | 1 | 1 |
| `parte_hh` | 1 | 1 | 1 | 2 | 1 |
| `presupuesto_material` | 1 | 1 | 1 | 1 | 1 |
| `vale_consumo` | 1 | 1 | 1 | 1 | 1 |

Esas celdas distintas de cero son las **44** líneas OK del reporte. La suma de todas las celdas, ceros incluidos, es **48**.

`hh_teorica_por_unidad` vacía sigue en silver. Si trae texto y el cast falla, la fila entera es `cast_fallido`.

---

## 7) Gold: estrella, cluster, sin partición

Los tres hechos clusterizan por `obra_id` y la segunda clave (`partida_id`, `cuadrilla_id` o `material_id`). **No** hay `PARTITION BY`.

Por qué: en el sandbox la partición vence a los 60 días **según la fecha de la partición**, no según el día en que se creó la tabla. El programa va de mayo a septiembre de 2026 y el calendario de la obra llega a noviembre. Partir por `semana_lunes` borraría las semanas viejas y la curva S se cortaría. El cluster no vence por fecha. La tabla entera igual expira a los 60 días de creada, y `make run` la reconstruye.

Gold no vuelve a limpiar. 735 avances son las 735 del programa silver y las 735 de la medición. 1.470 HH son los 1.470 partes. 882 consumos son los 882 presupuestos y los 882 vales. En esta semilla los dos lados del núcleo limpio vienen completos, así que el full outer no inventa ceros. `verify_gold` exige eso, 0 huérfanas contra las dimensiones, y la historia de la sección 4. La corrida real dio OK.

### Métricas SUM/SUM

Las tablas no guardan el porcentaje. Guardan montos y cantidades.

```text
% avance físico = SUM(monto_ejecutado) / SUM(monto_contrato)
SPI = SUM(monto_ejecutado) / SUM(monto_programado)
HH por unidad ejecutada = SUM(hh) / SUM(cantidad_ejecutada)
desviación de consumo = (SUM(monto_real) - SUM(monto_presupuestado)) / SUM(monto_presupuestado)
```

`monto_contrato` se suma en `d_partida`. HH por unidad solo dentro de una misma unidad. Entre materiales, la desviación es en montos a precio de presupuesto, no sumando kg con litros.

No marcar un monto como tipo Porcentaje en la fuente: Looker lo promedia.

---

## 8) Sandbox, sin facturación

Proyecto de lab: `csa-obra-jp`. Location: **US**. Datasets: `csa_bronze`, `csa_silver`, `csa_gold`.

| Permitido | No entra |
|---|---|
| Load job `WRITE_TRUNCATE` | `INSERT` / `UPDATE` / `DELETE` / `MERGE` |
| `CREATE OR REPLACE TABLE` | Streaming inserts |
| Expiración de la tabla a 60 días desde el `CREATE` | Partición por fecha en este horizonte |
| ADC (`gcloud auth application-default login`) | JSON de service account en el repo |

`GCP_PROJECT` es obligatorio. Si falta, el script se detiene. No hay proyecto hardcodeado.

`make run` reconstruye CSV, bronze, silver y gold desde cero. No depende de lo que haya quedado de la corrida anterior, porque a los 60 días el sandbox borra las tablas.

La conexión a SAP es relato. No hay host, usuario ni credencial.

---

## 9) Decisiones que hay que poder defender

1. **Tres granos, no uno.** La semana de la partida, el día de la cuadrilla y la semana del material no son la misma fila. Juntarlos duplica HH o toneladas.
2. **Bronze STRING, silver estricto.** El landing no es el contrato. Tipar en el load convierte un problema de calidad en un job fallido. La lección viene del `NO-CAST` de Meli. No subir `max_bad_records`.
3. **Un motivo por fila, en este orden.** Cast, nulo, duplicado, FK, fecha. Si la misma fila entra dos veces a la cuarentena, 4.819 deja de ser 4.771 + 48.
4. **FK contra la dimensión silver ya limpia.** Un padre en cuarentena no alcanza. El SQL de los hechos corre después de las dimensiones.
5. **Gold sin partición por fecha.** El sandbox vence la partición según su fecha. Cluster por `obra_id` y la segunda clave, que es el corte del dashboard.
6. **Montos aditivos, porcentaje al final.** Un `%` o un SPI guardado en la fila se promedia. `SUM(monto_ejecutado) / SUM(monto_programado)` pesa la obra grande más que la chica. Por eso el global es 0,90 y Hualpén sigue en 0,55.
7. **`monto_contrato` una vez, en `d_partida`.** Copiarlo en cada semana infla el denominador del % avance por la cantidad de semanas.
8. **HH por unidad solo dentro de una unidad.** Sin filtro de partida el ratio es nulo. `SUM(hh)` sí se puede mostrar: 42.707,7.

---

## 10) Preguntas probables + respuesta modelo

1. **¿Qué problema resuelve?** Un SSoT para el jefe de obra: avance contra el programa, HH por unidad y desviación de materiales, sin promediar porcentajes.
2. **¿Por qué medallón?** Bronze acepta el export. Silver decide si la fila sirve. Gold es lo que mira el dashboard. Looker no lee bronze.
3. **¿Por qué tres hechos?** Porque los granos no coinciden. El asfalto de la semana no es de una sola partida.
4. **¿Qué es el SPI?** `SUM(monto_ejecutado) / SUM(monto_programado)`, los dos valorizados al precio de contrato. No es un promedio de SPI semanales. 1 es ir al día.
5. **¿Por qué el % avance no es el SPI?** El avance compara con el monto del contrato. El SPI compara con lo programado. Los Batros: avance 0,56 y SPI 0,70. Las 21 semanas del extracto son el 80% del contrato.
6. **¿Por qué SUM/SUM?** Un 10% sobre 20 m³ no pesa lo mismo que un 10% sobre 2.000. El SPI global 0,90 esconde a Hualpén en 0,55.
7. **¿Por qué bronze es STRING?** Porque en Meli un BOOL rechazó `NO-CAST` y el job murió antes de la cuarentena. Acá el token entra y silver lo marca `cast_fallido`.
8. **¿Por qué no subes `max_bad_records`?** Perderías filas sin motivo. 4.819 = 4.771 + 48 dejaría de cerrar.
9. **¿Por qué un solo motivo?** La fila con `NO-CAST` y la clave vacía es un solo `cast_fallido`. Si la contara dos veces, la cuarentena pasaría de 48.
10. **¿48 cuarentenas y 44 conteos?** 48 es la suma de filas en `q_<tabla>`. 44 es la cantidad de celdas de motivo distintas de cero que `verify_silver` imprimió OK. Los ceros también calzan y no se imprimen. Huérfanas en silver: 0.
11. **¿Por qué la FK mira silver?** La obra también puede haber caído a cuarentena. Una partida que apunta a esa obra no tiene dimensión. Además, si la partida existe pero es de otra obra, también es `fk_huerfana`.
12. **¿Por qué no particionas el hecho?** La partición del sandbox vence a los 60 días según su fecha. Mayo a noviembre de 2026 se comería la curva. Cluster por `obra_id` y la segunda clave.
13. **¿Clustering ahorra bytes?** En este lab no hay demo de bytes. No inventar un porcentaje de prune. El cluster está para el corte del informe y para no borrar la historia.
14. **¿Por qué `d_fecha` tiene 208 días?** Del 2026-05-04 al 2026-11-27, vigencia de las obras, no solo las semanas del extracto.
15. **¿CTAS o MERGE?** Sandbox sin DML. `CREATE OR REPLACE` y load `WRITE_TRUNCATE`. `make run` rehace todo.
16. **¿Dónde están las credenciales?** En ningún archivo. ADC en la Mac. CI solo corre pytest.
17. **¿El SAP es real?** No. Es el relato del libro de obra. No hay host ni usuario.
18. **¿Qué falta?** El dashboard publicado. Hay guía de estilo y gold. No hay link ni capturas.

---

## 11) La lección que hay que decir en voz alta

El SPI global **0,90** (4.941.031.200 / 5.503.260.000) es un número correcto y, solo, es una mala respuesta. Hualpén está en **0,55** y Los Batros en **0,70**. Talcahuano va en **1,05** y empuja el total. Si alguien promedia el SPI de las siete obras, la obra chica pesa igual que la grande y el 0,90 deja de ser el de los montos.

Lo mismo pasa con los materiales: la desviación global es **0,0455**, y el asfalto de Coronel está en **0,40**. El total en plata no muestra el insumo que se pasó.

Por eso el dashboard abre con la tabla de obras, no con una sola tarjeta.

---

## 12) Checklist de repaso

- [ ] Pitch de 2 minutos: tres granos, medallón, SUM/SUM, sandbox, dashboard pendiente.
- [ ] Seed 42, extracto 2026-05-04 → 2026-09-21, vigencia hasta 2026-11-27, `d_fecha` de 208 días.
- [ ] Conteos: bronze 4.819, silver 4.771, cuarentena 48. 44 motivos distintos de cero OK. 0 huérfanas.
- [ ] Prioridad en orden: cast, nulo, duplicado, FK, fecha. La fila con `NO-CAST` y PK vacía es solo cast.
- [ ] Por qué bronze es STRING, y por qué no se sube `max_bad_records`.
- [ ] FK contra la dimensión silver ya limpia, no contra bronze.
- [ ] Números sin filtro: SPI 0,90, avance 0,72, desviación 0,0455. Los Batros 0,70 y 0,56. Talcahuano 1,05. Hualpén 0,55. Asfalto Coronel 0,40. HH 1,40 contra 0,80. `SUM(hh)` 42.707,7.
- [ ] Decir que el 0,90 esconde la dispersión.
- [ ] Por qué gold no tiene partición por fecha, y qué cluster sí tiene.
- [ ] Frase de sandbox: sin DML, solo `CREATE OR REPLACE` y load jobs, ADC, sin JSON en git.
- [ ] Decir en voz alta que el dashboard todavía no está publicado.

---

## Dashboard (pendiente)

Julio está armando el informe en Data Studio. **No hay viewer ni capturas** en el repo. No inventar un link.

Cuando exista, esta sección se completa con:

- Link público del reporte.
- Capturas por página: Resumen de obras, Avance vs programa, Productividad HH, Materiales y desviación.
- Valores leídos del informe, comparados con la sección 4 y con `looker/STYLE_GUIDE.md`. Si un número no calza, primero Restablecer filtros y confirmar que el campo es `SUM(monto_ejecutado) / SUM(monto_programado)` y no un `AVG`.

Hasta entonces, el plan de páginas, fórmulas y valores sin filtro está en [`looker/STYLE_GUIDE.md`](../looker/STYLE_GUIDE.md). Las fuentes son las tablas de `csa_gold` de la sección 7. Nada de bronze.

---

## Enlaces rápidos

| Recurso | Dónde |
|---|---|
| Modelo y grano | [`docs/modelo-datos.md`](modelo-datos.md) |
| Manifest (seed 42) | [`data/manifest.json`](../data/manifest.json) |
| Bronze STRING | [`docs/paso-02-bronze.md`](paso-02-bronze.md) |
| Silver y prioridad | [`docs/paso-03-silver.md`](paso-03-silver.md) |
| Gold, cluster, SUM/SUM | [`docs/paso-04-gold.md`](paso-04-gold.md) |
| Plan del dashboard | [`looker/STYLE_GUIDE.md`](../looker/STYLE_GUIDE.md) |
| Repo | https://github.com/JulioPradenas/csa-obra-bq |

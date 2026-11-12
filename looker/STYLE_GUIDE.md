# Guía de estilo Looker Studio — CSA Obra

> **Lab de portafolio. Marca con fines ilustrativos.**  
> Paleta inspirada en Ingeniería CSA (San Pedro de la Paz). Sin logos y sin letrero de marca. El informe se arma a mano sobre `csa_gold`. Esta guía es el contrato visual, con los valores sin filtro de la semilla 42.

Objetivo: que el jefe de obra lea avance contra programa, productividad HH y materiales con la misma fórmula en todas las páginas, números en es-CL y contraste AA.

Fuente de las métricas: [`docs/modelo-datos.md`](../docs/modelo-datos.md) y [`docs/paso-04-gold.md`](../docs/paso-04-gold.md). Si una fórmula de aquí no coincide con el modelo, manda el modelo. Los campos de Looker salen de `csa_gold`. Nada de bronze ni de `q_<tabla>`.

Los porcentajes se calculan como SUM/SUM, nunca como promedio de porcentajes.

---

## Plan de páginas

Cuatro páginas. Footer en todas con el aviso del lab. Sin logo. Sin cross-filter. Botón **Restablecer** visible.

Filtros comunes: **Obra** (`d_obra.obra_id`) y **Período**. En Avance vs programa el período es la semana de corte (`d_fecha.fecha` unida a `semana_lunes`): el acumulado suma desde el inicio de la obra hasta ese lunes. En Productividad HH el período filtra `f_hh_cuadrilla.fecha`. En Materiales filtra `f_consumo_material.semana_lunes`. Sin filtro, el corte es el horizonte completo del extracto (lunes 4/5/2026 al 21/9/2026).

| Página | Qué responde | Fuente | Gráfico |
|---|---|---|---|
| Resumen de obras | ¿Qué obra va atrasada y cuánto del contrato ya está hecho? | `f_avance_partida` + `d_obra` + `d_partida` | 4 KPI y tabla por obra |
| Avance vs programa | ¿La curva S y qué capítulo explica el atraso? | `f_avance_partida` + `d_partida` + `d_fecha` | Curva y barras |
| Productividad HH | ¿Cuántas HH se van por unidad y qué cuadrilla se aparta? | `f_hh_cuadrilla` + `d_cuadrilla` + `d_partida` | Tabla y barras |
| Materiales y desviación | ¿Dónde el consumo se aparta del presupuesto? | `f_consumo_material` + `d_material` + `d_proveedor` | KPI y barras |

### Resumen de obras

Fuente: `csa_gold.f_avance_partida`, `d_obra`, `d_partida`. El monto del contrato se suma en `d_partida`, una vez por partida.

| Bloque | Tipo | Campos | Color |
|---|---|---|---|
| KPI % avance físico | Tarjeta | `SUM(monto_ejecutado) / SUM(monto_contrato)` | Valor `#1F5C3F` |
| KPI SPI | Tarjeta | `SUM(monto_ejecutado) / SUM(monto_programado)` | Valor `#1F5C3F`. Semáforo del lab |
| KPI monto ejecutado | Tarjeta | `SUM(monto_ejecutado)` | `#1F5C3F` |
| KPI monto programado | Tarjeta | `SUM(monto_programado)` | `#1F5C3F` |
| Tabla de obras | Tabla | `obra_nombre`, comuna, `SUM(monto_ejecutado)`, `SUM(monto_programado)`, SPI, % avance | Texto `#333333`. SPI con semáforo |

Filtro de obra apagado en esta página: tiene que verse el ranking. Período: sin filtro = horizonte completo.

### Avance vs programa

| Bloque | Tipo | Campos | Color |
|---|---|---|---|
| Los mismos 4 KPI del Resumen | Tarjeta | Las fórmulas de arriba, con el filtro de esta página | `#1F5C3F` |
| Curva S | Serie de dos líneas por `semana_lunes` | Acumulado de `SUM(monto_programado)` y de `SUM(monto_ejecutado)` | Programado `#1F5C3F`, ejecutado `#2E7D57`. Referencia no va en `#FED501` |
| SPI por capítulo | Barras | `SUM(monto_ejecutado) / SUM(monto_programado)` dentro de cada `capitulo` | Relleno `#2E7D57`, borde `#1F5C3F` |
| Tabla partida | Tabla | unidad, `SUM(cantidad_programada)`, `SUM(cantidad_ejecutada)`, % avance, SPI | `#333333` |

El % avance de la tabla es `SUM(monto_ejecutado) / monto_contrato` de esa partida. `monto_contrato` entra una vez desde `d_partida`. La curva no promedia el SPI de cada semana: cada punto acumula las sumas y divide al final.

### Productividad HH

Fuente: `csa_gold.f_hh_cuadrilla`, `d_cuadrilla`, `d_partida`. Sin una partida elegida no hay una tarjeta única: mezclaría m³ con ml. La tarjeta de HH por unidad, sin filtro de partida, muestra `—`.

| Bloque | Tipo | Campos | Color |
|---|---|---|---|
| Tabla por partida | Tabla | `partida_nombre`, `unidad_nombre`, `SUM(hh)`, `SUM(cantidad_ejecutada)`, `SUM(hh) / SUM(cantidad_ejecutada)` | `#333333`. El ratio se calcula dentro de la fila, una unidad |
| KPI HH por unidad | Tarjeta, solo con una partida | `SUM(hh) / SUM(cantidad_ejecutada)` | `#1F5C3F` |
| KPI HH teórica | Tarjeta | `hh_teorica_por_unidad` de `d_partida`. No es un promedio | `#8A5200` si se dibuja la referencia |
| Barras por cuadrilla | Barras | El mismo `SUM(hh) / SUM(cantidad_ejecutada)`, cortado por `cuadrilla_nombre` | `#2E7D57` |

Filtros: obra, partida, período sobre `fecha`. La HH teórica, si viene nula, no se dibuja.

### Materiales y desviación

Fuente: `csa_gold.f_consumo_material`, `d_material`, `d_proveedor`, `d_obra`. El rollup entre materiales es en montos, a precio de presupuesto.

| Bloque | Tipo | Campos | Color |
|---|---|---|---|
| KPI desviación | Tarjeta | `(SUM(monto_real) - SUM(monto_presupuestado)) / SUM(monto_presupuestado)` | `#1F5C3F`. Semáforo del lab |
| KPI monto real | Tarjeta | `SUM(monto_real)` | `#1F5C3F` |
| KPI monto presupuestado | Tarjeta | `SUM(monto_presupuestado)` | `#1F5C3F` |
| Barras por familia | Barras | La desviación, `SUM / SUM` dentro de cada `familia` | `#2E7D57` |
| Barras por proveedor | Barras | La misma fórmula por `proveedor_nombre` | `#1F5C3F` |
| Tabla material | Tabla | unidad, cantidades, desviación en monto. La desviación en cantidad solo en la fila de un material | `#333333` |

Filtros: obra, familia, material, proveedor, semana. El subtítulo de la tarjeta dice «a precio de presupuesto».

---

## Valores esperados sin filtro

Semilla 42, botón Restablecer, horizonte completo. Sirven para validar el informe recién conectado. Los montos son CLP enteros. La tarjeta redondea; el control es la división de las sumas.

| Control | Esperado |
|---|---|
| Obras en `d_obra` | 7 |
| Filas `f_avance_partida` | 735 |
| Filas `f_hh_cuadrilla` | 1.470 |
| Filas `f_consumo_material` | 882 |
| Filas `d_fecha` | 208 (4/5/2026 a 27/11/2026) |
| `SUM(monto_ejecutado)` | 4.941.031.200 |
| `SUM(monto_programado)` | 5.503.260.000 |
| `SUM(monto_contrato)` en `d_partida` | 6.879.075.000 |
| SPI sin filtro | 4.941.031.200 / 5.503.260.000 = 0,8978. Tarjeta a 2 decimales: **0,90** |
| % avance físico sin filtro | 4.941.031.200 / 6.879.075.000 = 0,7183. Tarjeta a 1 decimal: **71,8%** |
| `SUM(monto_real)` | 2.430.951.600 |
| `SUM(monto_presupuestado)` | 2.325.111.600 |
| Desviación sin filtro | (2.430.951.600 − 2.325.111.600) / 2.325.111.600 = 0,0455. Tarjeta: **4,6%** |
| `SUM(hh)` | 42.707,70 |
| HH por unidad sin filtro de partida | `—` (hay más de una unidad) |

En la tabla de obras, sin click adicional:

| Obra | SPI | % avance físico |
|---|---:|---:|
| Reposición calzada Los Batros, San Pedro de la Paz | **0,70** | **0,56** |
| Conservación costanera Talcahuano | **1,05** | **0,84** |
| Conservación ruta Hualpén (paralizada) | **0,55** | |

Materiales, fila cemento asfáltico de la reposición de Coronel (`OBR-05`, `MAT-ASF`, partida carpeta `PAR-05-203`): desviación **0,40**. El cemento de esa misma obra queda en 0.

Productividad, cuadrilla de tierras: Los Batros **1,40** HH por unidad; Talcahuano **0,80**. Son `SUM(hh) / SUM(cantidad_ejecutada)` dentro de esa cuadrilla, no un promedio de días.

---

## Fórmulas canónicas

Se escriben igual que en el modelo. Los nombres son medidas aditivas del hecho, no porcentajes guardados.

```text
% avance físico = SUM(monto_ejecutado) / SUM(monto_contrato)

SPI = SUM(monto_ejecutado) / SUM(monto_programado)

HH por unidad ejecutada = SUM(hh) / SUM(cantidad_ejecutada)

desviación de consumo = (SUM(monto_real) - SUM(monto_presupuestado)) / SUM(monto_presupuestado)
```

Los porcentajes se calculan como SUM/SUM, nunca como promedio de porcentajes.

Tipo de campo en Looker: **Porcentaje** para el % avance y la desviación, **Número** para el SPI y para las HH por unidad. El 0/1 no existe en estos hechos. No marques un monto como porcentaje dentro de la fuente.

Si el denominador es 0, la tarjeta muestra `—`.

---

## 1. Tokens de diseño

Amarillo `#FED501`. Verde profundo `#1F5C3F`. Verde medio `#2E7D57`. Gris `#333333`. El amarillo es fondo de header y relleno de superficie grande. No es color de texto ni de línea fina: sobre blanco queda en 1,43 : 1.

| Token | Valor |
|---|---|
| Fondo página | `#F4F6F3` |
| Superficie de card | `#FFFFFF` |
| Amarillo (header / franja grande) | `#FED501` |
| Verde profundo (texto de header, serie, filete, valor KPI) | `#1F5C3F` |
| Verde medio (relleno de barra, segunda serie) | `#2E7D57` |
| Texto | `#333333` |
| Texto secundario | `#4E5852` |
| Líneas / bordes | `#D5DDD6` |
| Verde semáforo (texto) | `#1F5C3F` — fondo `#E5F4EC` |
| Ámbar semáforo (texto) | `#8A5200` — fondo `#FFF4E0` |
| Rojo semáforo (texto) | `#9C2F2F` — fondo `#FDECEC` |
| Fuente | **Roboto** en el tema de Looker Studio. El informe no depende de una webfont externa |
| Label KPI | 11px, uppercase, weight 600, color `#4E5852` |
| Valor KPI | 28–32px, weight 700, color `#1F5C3F` |
| Título card | 14px, weight 600, color `#333333` |
| Tabla | 13px |
| Radio cards | 12px |
| Sombra | suave (`0 1px 2px` + `0 8px 24px` a ~6% de `#1F5C3F`) |
| Grilla | 12 columnas, gutter **24px**, margen de página 24px |
| Header | **64px**, fondo `#FED501`, texto `#1F5C3F`, **filete inferior 2px** `#1F5C3F` |
| Footer | 32px, texto `#4E5852`: «Lab de portafolio. Marca con fines ilustrativos.» |

Título de texto del header: «Avance de obra · programa, HH y materiales». Sin logo.

### Contraste AA

Ratios con la fórmula de luminancia relativa de WCAG 2.x. Umbral de texto normal: **4,5 : 1**. El semáforo no se comunica solo con color: la celda lleva el número y, en la leyenda, el rótulo.

| Texto | Fondo | Ratio | Uso |
|---|---|---|---|
| `#1F5C3F` | `#FFFFFF` | 7,89 : 1 | Valores KPI, series, links |
| `#1F5C3F` | `#F4F6F3` | 7,26 : 1 | Texto sobre el fondo de página |
| `#1F5C3F` | `#FED501` | 5,54 : 1 | Título y controles del header |
| `#FFFFFF` | `#1F5C3F` | 7,89 : 1 | Texto sobre verde profundo |
| `#333333` | `#FFFFFF` | 12,63 : 1 | Cuerpo |
| `#333333` | `#F4F6F3` | 11,63 : 1 | Cuerpo sobre el fondo |
| `#333333` | `#FED501` | 8,86 : 1 | Texto gris sobre amarillo, si hiciera falta. El header usa `#1F5C3F` |
| `#4E5852` | `#FFFFFF` | 7,39 : 1 | Label KPI, ejes, footer |
| `#4E5852` | `#F4F6F3` | 6,80 : 1 | Label sobre el fondo de página |
| `#2E7D57` | `#FFFFFF` | 5,02 : 1 | Verde medio como texto, solo si hace falta. El KPI va en `#1F5C3F` |
| `#FFFFFF` | `#2E7D57` | 5,02 : 1 | Texto sobre una barra verde |
| `#1F5C3F` | `#E5F4EC` | 6,95 : 1 | Semáforo en meta |
| `#8A5200` | `#FFF4E0` | 5,86 : 1 | Semáforo en el borde |
| `#9C2F2F` | `#FDECEC` | 6,43 : 1 | Semáforo fuera de meta |
| `#FFFFFF` | `#FED501` | 1,43 : 1 | No usar |
| `#FED501` | `#FFFFFF` | 1,43 : 1 | El amarillo no es color de texto ni de línea fina |
| `#2E7D57` | `#FED501` | 3,52 : 1 | No usar el verde medio como texto sobre el header |

Líneas de gráfico sobre fondo claro: `#1F5C3F`. Una referencia (la HH teórica, el SPI = 1) va en `#8A5200` discontinua. El relleno de una barra ancha puede ser `#2E7D57` o `#FED501` con borde `#1F5C3F`.

---

## 2. KPI cards

Orden en Avance vs programa: % avance físico, SPI, monto ejecutado acumulado, monto programado acumulado.

Cada card lleva la fórmula de «Fórmulas canónicas» en la descripción del campo. El número no va solo.

Polaridad del delta (período contra el período anterior). Verde no significa «subió»:

| Tarjeta | Lectura del movimiento |
|---|---|
| % avance físico | Subir es más obra ejecutada |
| SPI | Subir es acercarse o pasarse del programa. Bajar es atraso |
| HH por unidad ejecutada | Bajar es menos HH por unidad, dentro de la misma partida |
| Desviación de consumo | Bajar es acercarse al presupuesto o consumir menos |

El delta compara el mismo SUM/SUM en los dos períodos. Las bandas de color de abajo son un **borrador de diseño del lab**. No son un estándar de la marca y se mueven en el paso gold, cuando existan datos. No se mueven en silencio dentro de un gráfico.

| Medida | En meta | Atención | Fuera |
|---|---|---|---|
| SPI | `≥ 1` | `≥ 0,90` y `< 1` | `< 0,90` |
| Desviación de consumo | `≤ 0` | `> 0` y `≤ 0,05` | `> 0,05` |

En este borrador, un SPI sobre 1 queda en meta: la alerta que se pinta es el atraso. Una desviación muy negativa también queda en meta. Separar el adelanto fuerte y el subconsumo fuerte queda para el paso gold.
| HH por unidad | `≤` HH teórica | `≤ 1,10` × HH teórica | sobre eso |

Si `hh_teorica_por_unidad` es nula, la fila de HH no se pinta. El % avance físico no lleva semáforo: sin el programa, «más avance» no dice si la obra va atrasada. El semáforo de esa página está en el SPI.

---

## 3. Formato de números es-CL

Locale del informe: **Español (Chile)** (`es-CL`).

| Medida | Tipo en Looker | Ejemplo |
|---|---|---|
| % avance físico, desviación | Porcentaje, 1 decimal en card y 2 en tabla | `42,5%` |
| SPI | Número, 2 decimales | `0,96` |
| HH por unidad | Número, 1 decimal, con la unidad en el subtítulo | `1,8` HH/m³ |
| Montos CLP | Número, 0 decimales, miles con punto | `$ 1.250.000` |
| Cantidades | Número, 2 decimales | `1.250,50` |
| HH | Número, 1 decimal | `36,5` |
| Fecha | `dd/mm/yyyy` | `04/05/2026` |
| Nulo (denominador 0, o unidades mezcladas) | Guion | `—` |

Un cero de HH o de cantidad sí se muestra como `0`. El guion es para un ratio sin denominador.

---

## 4. Trampas conocidas

| Trampa | Qué pasa | Qué hacer |
|---|---|---|
| **Agregación por defecto AVG** | La tarjeta promedia un porcentaje ya cerrado y deja de cuadrar con la tabla | Fijar la métrica SUM/SUM en cada gráfico |
| **Promedio de porcentajes** | La partida chica pesa igual que la grande. El total no es el avance de la obra | Numerador y denominador aditivos. El % se cierra al final. Nunca como promedio de porcentajes |
| **SPI de la semana promediado** | El SPI del mes no es el promedio de los SPI semanales | Cada punto y la tarjeta vuelven a hacer `SUM(monto_ejecutado) / SUM(monto_programado)` |
| **`monto_contrato` repetido por semana** | El % avance se achica según cuántas semanas tenga la partida | El denominador se suma en `d_partida`, una vez por partida |
| **Unidades mezcladas** | HH/m³ con HH/ml, o kg con litros, producen un número que no existe | Si hay más de una `unidad_medida`, el KPI es `—`. El rollup entre materiales usa montos |
| **Cero en vez de nulo** | Una partida sin programa muestra SPI 0 y parece detenida del peor modo, o 0% de desviación parece perfecta | Denominador 0 → `—` |
| **Cuarentena dentro del KPI** | `q_<tabla>` «completa» el porcentaje con filas que silver ya sacó | Fuente del informe: gold |
| **Amarillo como texto** | `#FED501` sobre blanco queda en 1,43 : 1. No es AA | Amarillo solo en header y en rellenos grandes. Texto del header en `#1F5C3F` |
| **Verde medio sobre amarillo** | `#2E7D57` sobre `#FED501` queda en 3,52 : 1 | No es texto del header |
| **Verde = siempre hacia arriba** | Un alza de la desviación o de las HH por unidad se pinta como mejora | Invertir la polaridad en SPI hacia abajo, en HH por unidad y en desviación |
| **Cross-filter** | Un click en la curva vacía las tarjetas | Interacciones apagadas. Botón Restablecer |
| **Partir gold por fecha** | En el sandbox la partición vence a los 60 días y la curva pierde las semanas viejas | `CLUSTER BY`. El período es un filtro sobre `DATE` |

---

## 5. Checklist de armado

El informe se crea a mano en Looker Studio. Esta lista es el orden, en español de la UI.

1. Tema → fuente **Roboto**, fondo `#F4F6F3`.
2. Paleta: `#FED501`, `#1F5C3F`, `#2E7D57`, `#333333`.
3. Header 64px amarillo, texto `#1F5C3F`, filete `#1F5C3F` de 2px. En las cuatro páginas.
4. Locale **Español (Chile)**.
5. Cada tarjeta con la fórmula canónica y la polaridad de la sección 2.
6. Formato condicional solo en la celda de SPI, de desviación o de HH por unidad. No pintar la fila entera.
7. Serie y barras con `SUM / SUM` dentro del punto. Sin una columna de porcentaje precalculado.
8. Footer: «Lab de portafolio. Marca con fines ilustrativos.»
9. Sin logo y sin letrero de marca.

### Verificación final

Abrir el informe, **Restablecer** filtros y comprobar lo siguiente contra la tabla «Valores esperados sin filtro».

| Comprobación | Esperado |
|---|---|
| Fuente de las cuatro páginas | Gold. Nada de bronze ni de `q_<tabla>` |
| SPI Los Batros | 0,70 |
| Desviación asfalto Coronel | 0,40 |
| SPI sin filtro | 0,90 en la tarjeta (sumas 4.941.031.200 / 5.503.260.000) |
| % avance físico | `SUM(monto_ejecutado) / SUM(monto_contrato)`, con el contrato una vez por partida |
| SPI | `SUM(monto_ejecutado) / SUM(monto_programado)` en la tarjeta y en cada punto de la serie |
| HH por unidad ejecutada | `SUM(hh) / SUM(cantidad_ejecutada)`, con una sola unidad en el filtro |
| Desviación de consumo | `(SUM(monto_real) - SUM(monto_presupuestado)) / SUM(monto_presupuestado)` |
| Locale | es-CL: miles con punto, decimales con coma, fechas `dd/mm/yyyy` |
| Contraste | Texto de header `#1F5C3F` sobre `#FED501`. Ningún texto en `#FED501` |
| Aviso | El footer de cada página dice «Lab de portafolio. Marca con fines ilustrativos.» |
| Marca | No hay logo ni letrero de marca |

---

## Archivos de referencia

| Archivo | Uso |
|---|---|
| [`docs/modelo-datos.md`](../docs/modelo-datos.md) | Grano, indicadores y fórmulas que esta guía no reescribe |
| [`README.md`](../README.md) | Objetivo del lab, preguntas y roadmap |
| Esta guía | Tokens, contraste AA, páginas finales, valores sin filtro, es-CL |
| [`docs/paso-04-gold.md`](../docs/paso-04-gold.md) | Conteos gold y cómo correr `make run` en la Mac |

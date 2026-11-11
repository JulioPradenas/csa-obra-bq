# Paso 4 — Gold para el jefe de obra

> **Lab de portafolio. Marca con fines ilustrativos.**

**Dataset:** `csa_gold` · **location:** `US` · **expiración:** 60 días.  
**Entrada:** solo `csa_silver`. Ni bronze ni `q_<tabla>`.  
**Salida:** seis dimensiones y tres hechos. Sin partición por fecha. `CLUSTER BY`.

## Qué

La estrella que lee Looker Studio. Los hechos guardan cantidades y montos. El porcentaje se cierra en el gráfico:

```text
% avance físico = SUM(monto_ejecutado) / SUM(monto_contrato)
SPI = SUM(monto_ejecutado) / SUM(monto_programado)
HH por unidad ejecutada = SUM(hh) / SUM(cantidad_ejecutada)
desviación de consumo = (SUM(monto_real) - SUM(monto_presupuestado)) / SUM(monto_presupuestado)
```

`monto_contrato` vive en `d_partida`, una vez por partida. No va repetido en cada semana de `f_avance_partida`.

## Por qué no hay partición por fecha

En el sandbox la partición expira a los 60 días según su fecha. El horizonte de esta obra va de mayo a noviembre de 2026: las semanas viejas desaparecerían y la curva S se cortaría. `CLUSTER BY obra_id` (y la segunda clave del hecho) deja la tabla entera viva hasta que `make run` la vuelve a crear.

No hay DML ni streaming. Cada objeto es `CREATE OR REPLACE TABLE … AS SELECT`.

## Grano

| Tabla | Grano | Cluster |
|---|---|---|
| `d_obra` | 1 obra | `obra_id` |
| `d_proveedor` | 1 proveedor | `proveedor_id` |
| `d_partida` | 1 partida | `obra_id, partida_id` |
| `d_cuadrilla` | 1 cuadrilla | `obra_id, cuadrilla_id` |
| `d_material` | 1 material | `material_id, proveedor_id` |
| `d_fecha` | 1 día | `fecha` |
| `f_avance_partida` | obra × partida × semana | `obra_id, partida_id` |
| `f_hh_cuadrilla` | obra × cuadrilla × día | `obra_id, cuadrilla_id` |
| `f_consumo_material` | obra × material × semana | `obra_id, material_id` |

`f_avance_partida` es el full outer de programa y medición silver. El lado que falta entra como 0, no como NULL. `f_consumo_material` hace lo mismo con presupuesto y vale. `f_hh_cuadrilla` es el parte silver, una fila por día de cuadrilla.

`d_fecha` se arma con `GENERATE_DATE_ARRAY` desde el `fecha_inicio` más temprano hasta el `fecha_termino` más tardío. En esta semilla son 208 días, del 4/5/2026 al 27/11/2026.

## Esperados (semilla 42)

La simulación local (`scripts/gold_sim.py`) y `verify_gold` usan estas anclas. Los montos son la suma, sin redondear.

| Tabla | Filas |
|---|---:|
| `d_obra` | 7 |
| `d_proveedor` | 5 |
| `d_partida` | 35 |
| `d_cuadrilla` | 14 |
| `d_material` | 6 |
| `d_fecha` | 208 |
| `f_avance_partida` | 735 |
| `f_hh_cuadrilla` | 1.470 |
| `f_consumo_material` | 882 |

| Control | Valor |
|---|---|
| `SUM(monto_ejecutado)` | 4.941.031.200 |
| `SUM(monto_programado)` | 5.503.260.000 |
| `SUM(monto_contrato)` | 6.879.075.000 |
| SPI sin filtro | 0,8978 (tarjeta 0,90) |
| % avance físico sin filtro | 0,7183 (tarjeta 71,8%) |
| `SUM(monto_real)` | 2.430.951.600 |
| `SUM(monto_presupuestado)` | 2.325.111.600 |
| Desviación sin filtro | 0,0455 (tarjeta 4,6%) |
| `SUM(hh)` | 42.707,70 |
| SPI Los Batros (`OBR-01`) | **0,70** |
| % avance Los Batros | **0,56** |
| SPI Talcahuano (`OBR-02`) | **1,05** |
| SPI Hualpén (`OBR-06`) | **0,55** |
| Desviación asfalto Coronel (`OBR-05`, `MAT-ASF`) | **0,40** |
| HH/unidad tierras Los Batros | **1,40** |
| HH/unidad tierras Talcahuano | **0,80** |
| Huérfanas contra dimensiones | 0 |

735 filas de avance = las 735 del programa silver = las 735 de la medición silver. 1.470 partes = 1.470 filas de HH. 882 presupuestos = 882 vales = 882 filas de consumo. El lado que falta no aparece en esta semilla: el generador escribe los dos lados del núcleo limpio.

## Correrlo en la Mac

```bash
cd /Users/julio/csa-obra-bq
git fetch origin
git checkout cursor/paso-04-gold-f154
source .venv/bin/activate
pip install -r requirements.txt
export GCP_PROJECT=csa-obra-jp
make run
```

`make run` regenera CSV, bronze, silver y gold, y corre las tres verificaciones. `pip install` hace falta solo si cambió `requirements.txt`. Este paso no agrega paquetes.

Sin tocar GCP:

```bash
make run DRY=1
```

`verify_gold` imprime la tabla de filas, las anclas y `RESULTADO: OK` o `RESULTADO: FALLA`. No abre cliente de BigQuery. La corrida real usa ADC. No hay llave de service account en el repo.

El armado del informe, con estos mismos números, está en [`looker/STYLE_GUIDE.md`](../looker/STYLE_GUIDE.md).

## Cómo se verificó

No hay credenciales GCP en el entorno del agente. No se ejecutó el `CREATE OR REPLACE` contra `csa-obra-jp`.

- `make test` exige `CLUSTER BY`, ausencia de partición en el SQL, las fórmulas SUM/SUM en la guía y que la simulación reproduzca 0,70 y 0,40.
- `make run DRY=1` termina en `RESULTADO: OK` en bronze, silver y gold.

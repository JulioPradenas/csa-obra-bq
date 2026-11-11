# Paso 3 — Silver tipado y cuarentena

> **Lab de portafolio. Marca con fines ilustrativos.**

**Dataset:** `csa_silver` · **location:** `US` · **expiración:** 60 días.  
**Entrada:** `csa_bronze`, todo STRING NULLABLE.  
**Salida:** una tabla tipada por entidad y `q_<tabla>` con la fila cruda en STRING, un motivo y la regla.

## Qué

Pasar del landing crudo a silver con tipo, una fila por llave natural y FK que existen en la dimensión ya limpia. Ninguna fila de bronze desaparece: o queda en silver o queda en cuarentena.

Archivos: `sql/silver/NN_<tabla>.sql` y `scripts/build_silver.py`. La simulación local es `scripts/motivos.py` (la misma prioridad, sobre los CSV). `scripts/verify_silver.py` compara esa clasificación con `data/manifest.json`.

## Por qué

Bronze acepta `NO-CAST`, `12,5` y `activo = SI` para que el load no aborte. Si el dashboard leyera eso, un precio ilegible entraría al monto. Silver es el contrato. La cuarentena explica lo que se sacó, con un conteo que cierra: `bronze = silver + q_<tabla>`.

En el sandbox no hay `MERGE` ni `UPDATE`. La transformación es `CREATE OR REPLACE TABLE … AS SELECT`. A los 60 días el sandbox borra las tablas. `make run` las vuelve a crear.

## El manifiesto no se recontó

El manifest del paso 2 ya guarda el **motivo ganador**, no cada defecto por separado. Lo arma `clasificar()` con esta prioridad:

```text
cast_fallido > nulo_obligatorio > duplicado > fk_huerfana > fecha_incoherente
```

La fila de `obras` que trae `fecha_inicio = NO-CAST` y `obra_id` vacío cuenta **solo** en `cast_fallido` (2 en obras, no 3). El paso 3 volvió a correr la misma clasificación sobre los CSV y los conteos calzan con el manifest. No hubo diferencia que corregir. Si más adelante una fila nueva trae dos defectos y el manifest la parte en dos, `verify_silver` imprime `RESULTADO: FALLA` y hay que cambiar el manifest a la vista, no esconder el delta.

## Cómo

Orden de build, porque la FK se valida contra la dimensión **silver**:

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

Cada archivo hace dos `CREATE OR REPLACE`: la tabla limpia y `q_<tabla>`.

En cada fila:

- `TRIM`. Ids a mayúsculas. Catálogos a minúsculas.
- Fechas con `SAFE_CAST` a `DATE`. Cantidades, HH y precios con `SAFE_CAST` a `NUMERIC`.
- `activo` acepta `true` / `True` / `1` y `false` / `False` / `0`. Otro texto no vacío es `cast_fallido`. No se usa `SAFE_CAST` a BOOL: BigQuery no trata el `'1'` como el contrato de este lab.
- Un código fuera del catálogo, con texto, es `cast_fallido`.
- Dedup con `ROW_NUMBER()` sobre la llave natural, solo entre filas que ya pasaron cast y nulos. Se queda la de menor id. La copia va a cuarentena.
- FK contra silver. Si la partida o la cuadrilla existe pero es de otra obra, también es `fk_huerfana`.
- `fecha_incoherente` al final: término antes del inicio, `semana_lunes` que no es lunes (en BigQuery el lunes es `EXTRACT(DAYOFWEEK) = 2`), o fecha fuera de la vigencia de la obra silver.

`hh_teorica_por_unidad` vacía sigue en silver. Si trae texto y el cast falla, la fila entera es `cast_fallido`.

## Esperados (semilla 42)

Silver = núcleo limpio. `q` = filas extra. La suma es el bronze.

| Tabla | Bronze | Silver | q |
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

| Tabla | cast_fallido | nulo_obligatorio | duplicado | fk_huerfana | fecha_incoherente |
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

`huerfanas_en_silver` tiene que ser 0. `verify_silver` imprime las dos tablas y `RESULTADO: OK` o `RESULTADO: FALLA`.

## Correrlo en la Mac

```bash
cd /Users/julio/csa-obra-bq
git fetch origin
git checkout cursor/paso-03-silver-f154
source .venv/bin/activate
pip install -r requirements.txt
export GCP_PROJECT=csa-obra-jp
make run
```

`pip install` hace falta solo si cambió `requirements.txt`. En este paso no se agregó un paquete: sigue pytest y el cliente de BigQuery.

Sin tocar GCP:

```bash
make run DRY=1
```

Eso regenera los CSV, hace dry-run de bronze y de silver, y clasifica en local. No abre cliente de BigQuery. Auth, cuando la corrida es real, es ADC. No hay llave de service account en el repo.

## Cómo se verificó

No hay credenciales GCP en el entorno del agente. No se ejecutó el `CREATE OR REPLACE` contra `csa-obra-jp`.

- `make test` incluye la simulación local contra el manifest, el orden de los cinco motivos en cada SQL, `SAFE_CAST` donde hay fecha o número, y `make run` apuntando a silver.
- `make run DRY=1` imprime `RESULTADO: OK` en bronze y en silver, con `huerfanas_en_silver 0`.

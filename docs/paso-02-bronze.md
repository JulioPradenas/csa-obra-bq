# Paso 2 — CSV sintéticos y bronze en sandbox

> **Lab de portafolio. Marca con fines ilustrativos.**

**Proyecto GCP del lab:** `csa-obra-jp` (solo por `GCP_PROJECT`; el código no lo asume).  
**Dataset:** `csa_bronze` · **location:** `US` · **expiración:** 60 días.  
**Semilla:** 42 · **horizonte del extracto:** 2026-05-04 → 2026-09-21 · **zona:** `America/Santiago`.  
**Vigencia de las obras:** 2026-05-04 → 2026-11-27.

El grano y las columnas salen de [modelo-datos.md](modelo-datos.md). Este paso no abre silver ni gold.

---

## Qué

Siete obras viales ficticias en comunas reales del Biobío, con partidas, cuadrillas, materiales y proveedores, más el programa, la medición, el parte diario y la bodega. Todo en CSV reproducible.

- `scripts/generar_datos.py` escribe `data/raw/*.csv` y `data/manifest.json`.
- `sql/bronze/ddl.sql` + `scripts/apply_ddl.py` crean el dataset y reemplazan las tablas.
- `scripts/load_bronze.py` las llena con un load job.
- `scripts/verify_bronze.py` compara manifest, CSV y, en la corrida real, `num_rows`. Imprime `RESULTADO: OK` o `RESULTADO: FALLA`.

El DDL de bronze es **todo STRING NULLABLE**. El tipo se aplica en silver con `SAFE_CAST`.

## Por qué bronze es todo STRING

El load de BigQuery parsea el CSV contra el tipo de la columna y, con `max_bad_records=0`, aborta el job entero si un valor no entra. En Meli un `NO-CAST` en un BOOL dejó afuera seis tablas: la cuarentena nunca vio la fila. Subir `max_bad_records` las perdería en silencio.

Aquí el landing acepta el texto, incluidos `NO-CAST`, `12,5`, `2026-02-31` y `activo = SI`. Silver decide el motivo. `DRY=1` valida el header y el conteo; el test del schema mira el valor contra el tipo del job.

## Historia que tiene que verse

Sobre las filas que sobreviven la prioridad (el núcleo limpio). El corte es el lunes 2026-09-21. Las 21 semanas del extracto son el 80% de la cantidad de contrato: por eso el % avance físico y el SPI no son el mismo número.

| Obra | Comuna | SPI | % avance físico al corte |
|---|---|---:|---:|
| Reposición calzada Los Batros (`OBR-01`, en ejecución) | San Pedro de la Paz | **0,70** | **0,56** |
| Conservación costanera Talcahuano (`OBR-02`) | Talcahuano | **1,05** | **0,84** |
| Conservación ruta Hualpén (`OBR-06`, paralizada) | Hualpén | **0,55** | — |

La cuadrilla de tierras de Los Batros rinde **1,40 HH por unidad**. La de Talcahuano, **0,80**. Es `SUM(hh) / SUM(cantidad_ejecutada)` dentro de la misma partida, no un promedio de rendimientos diarios.

Sobreconsumo: cemento asfáltico (`MAT-ASF`) en la reposición de Coronel (`OBR-05`). Desviación **0,40**. El resto de los materiales de esa obra calza con el presupuesto. El vale es obra × material × semana; el residente atribuye el asfalto de más a la partida `PAR-05-203` (carpeta asfáltica). El grano no prorratea el material entre partidas.

Los nombres de obras, mandantes, cuadrillas y proveedores son ficticios. Las comunas son reales: San Pedro de la Paz, Talcahuano, Concepción, Chiguayante, Coronel, Hualpén y Los Ángeles.

## Sandbox

| Permitido | No entra |
|---|---|
| Load job `WRITE_TRUNCATE` (`load_table_from_file`) | `INSERT` / `UPDATE` / `DELETE` / `MERGE` |
| `CREATE OR REPLACE TABLE` | Streaming inserts (`insert_rows`) |
| Expiración de tablas a 60 días | Una expiración más larga |

No hay `ALTER`. Si el shape cambia, `CREATE OR REPLACE` deja la tabla vacía y el load la vuelve a llenar. Location `US`. Auth: Application Default Credentials en la Mac de Julio. Si `GCP_PROJECT` no está exportado, el script se detiene. No hay proyecto por defecto y no hay llave de service account.

La conexión a SAP sigue siendo relato. Estos CSV no salen de un ERP.

## Cómo correrlo en la Mac

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

gcloud auth application-default login
export GCP_PROJECT=csa-obra-jp
make run
```

Sin tocar GCP:

```bash
make data          # escribe data/raw/*.csv y data/manifest.json
make run DRY=1     # regenera CSV + dry-run de DDL, load y verificación
make test          # pytest, sin ADC
```

En CI, `DRY` parte en 1. `make test` no llama a BigQuery.

| Target | Qué hace |
|---|---|
| `make data` | Regenera CSV (semilla 42) y `data/manifest.json`. Los CSV no se commitean. |
| `make bronze` | `CREATE OR REPLACE` de las 10 tablas y load `WRITE_TRUNCATE`. |
| `make run` | Lo anterior y la tabla manifest / csv / bq con `RESULTADO: OK` o `RESULTADO: FALLA`. |
| `make run DRY=1` | Regenera CSV, imprime el DDL y valida headers. No llama a BigQuery. |

El load usa schema explícito STRING, `skip_leading_rows=1`, `autodetect=False`, `max_bad_records=0`.

## Conteos bronze (semilla 42)

`row_counts` es lo que `num_rows` tiene que igualar. `clean_counts` es lo que queda si silver aplica la prioridad. La suma de los motivos es la diferencia.

| Tabla | Limpio | Bronze |
|---|---:|---:|
| `obras` | 7 | 12 |
| `proveedores` | 5 | 8 |
| `partidas` | 35 | 39 |
| `cuadrillas` | 14 | 18 |
| `materiales` | 6 | 10 |
| `programa_avance` | 735 | 742 |
| `medicion_avance` | 735 | 740 |
| `parte_hh` | 1.470 | 1.476 |
| `presupuesto_material` | 882 | 887 |
| `vale_consumo` | 882 | 887 |
| **Total** | **4.771** | **4.819** |

## Suciedad

Cada tipo es un número de **filas extra**, con un solo motivo ganador. El núcleo limpio no se muta. Una fila de `obras` trae `fecha_inicio = NO-CAST` y `obra_id` vacío a la vez: el motivo es `cast_fallido`, no los dos.

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

Prioridad, la misma que usará silver:

```text
cast_fallido > nulo_obligatorio > duplicado > fk_huerfana > fecha_incoherente
```

Ejemplos plantados: `NO-CAST`, decimal `"12,5"`, fecha `2026-02-31`, `activo = SI`, tipo `demolicion`, centinelas `OBR-HUERFANA`, `PAR-HUERFANA`, `CUA-HUERFANA`, `MAT-HUERFANA`, `PRV-HUERFANO`, una partida de OBR-02 imputada a OBR-01, `semana_lunes = 2026-05-06` (miércoles) y `2026-04-06` (lunes anterior al inicio). `2026-05-04` es un lunes válido del horizonte, no suciedad.

`obras` y `proveedores` no tienen padre, así que su `fk_huerfana` es 0. Las dimensiones sin fecha quedan en 0 en `fecha_incoherente`. Los ceros van en el manifest para que el paso 3 no crea que un motivo se olvidó.

## Cómo se verificó

En el entorno del agente **no hay credenciales GCP**. No se ejecutó el load ni el `CREATE OR REPLACE` contra `csa-obra-jp`.

Lo que sí corrió: `make test` y `make run DRY=1`. El dry-run imprime `RESULTADO: OK` y no abre cliente de BigQuery.

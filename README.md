# CSA — Avance de obra vial en BigQuery

> **Lab de portafolio. Marca con fines ilustrativos.**  
> No es un entregable de Ingeniería CSA ni un claim sobre sus obras. Sin logos.

Analista: [Julio Pradenas](https://github.com/JulioPradenas)

Proyecto 3 del portafolio Analista BI.  
Proyecto 1: [kora-logistica-bq](https://github.com/JulioPradenas/kora-logistica-bq).  
Proyecto 2: [meli-fulfillment-bq](https://github.com/JulioPradenas/meli-fulfillment-bq).

## Objetivo

Un número por KPI para el jefe de obra, en una obra vial del Gran Concepción: avance físico contra el contrato, SPI contra el programa, horas hombre (HH) por unidad ejecutada y desviación de materiales. Los porcentajes se cierran con SUM/SUM.

## Preguntas de negocio

1. ¿Cuánto del contrato ya está ejecutado, y cómo se compara con lo programado a la semana de corte?
2. ¿Qué capítulo o partida explica el atraso?
3. ¿Cuántas HH se van por unidad en la partida, y qué cuadrilla rinde distinto?
4. ¿En qué material o proveedor el consumo se aparta del presupuesto?

Fórmulas: [docs/modelo-datos.md](docs/modelo-datos.md).

## Solución

```text
CSV sintéticos → bronze → silver (y q_<tabla>) → gold → Looker Studio
```

- **Hechos:** `f_avance_partida`, `f_hh_cuadrilla`, `f_consumo_material`.
- **Proyecto GCP:** el de `GCP_PROJECT`. No hay default. En la Mac el nombre es `csa-obra-jp`.
- **Datasets:** `csa_bronze` y `csa_silver` (con `q_<tabla>`). `csa_gold` sigue pendiente. Location `US`.
- **Zona horaria:** `America/Santiago`.
- **Expiración:** 60 días. Sin DML ni streaming. Gold va con `CLUSTER BY`, sin partición por fecha.
- **ERP:** el relato habla de un SAP de obra. No hay conexión. El bronze es CSV sintético.

## Roadmap

| Paso | Entrega | Estado |
|---|---|---|
| 1 | Esqueleto, modelo de datos, guía de estilo | listo |
| 2 | CSV sintéticos y bronze | listo |
| 3 | Silver y cuarentena | listo |
| 4 | Gold para el jefe de obra | este paso |
| 5 | Looker Studio según la guía | pendiente |

`make run` regenera los CSV y reconstruye bronze, silver y gold. En CI, `DRY` parte en 1 y esa corrida no llama a BigQuery. `make test` tampoco.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
make test
```

## Paso 2 — correrlo en la Mac

El proyecto `csa-obra-jp` está pensado para **BigQuery sandbox, sin facturación**. No hay DML ni streaming inserts. El camino es load job `WRITE_TRUNCATE` y `CREATE OR REPLACE`. Las tablas expiran a los 60 días.

```bash
gcloud auth application-default login
export GCP_PROJECT=csa-obra-jp
make run
```

`GCP_PROJECT` es obligatorio. Si falta, el script se detiene: no hay proyecto por defecto. Auth solo con ADC. No uses una llave de service account.

Sin tocar GCP:

```bash
make data          # escribe data/raw/*.csv y data/manifest.json
make run DRY=1     # regenera CSV + dry-run de DDL, load y verificación
```

`make run DRY=1` termina en `RESULTADO: OK` si el manifest cuadra con los CSV y con la cuarentena. Conteos de bronze: [docs/paso-02-bronze.md](docs/paso-02-bronze.md). Silver y la tabla de esperados: [docs/paso-03-silver.md](docs/paso-03-silver.md).

## Docs

- [Modelo de datos](docs/modelo-datos.md) — grano, fórmulas, suciedad planeada, sandbox
- [Paso 2 — bronze sandbox](docs/paso-02-bronze.md) — CSV, anomalías, load job, límite de 60 días
- [Paso 3 — silver y cuarentena](docs/paso-03-silver.md) — SAFE_CAST, un motivo por fila, conteos
- [Paso 4 — gold](docs/paso-04-gold.md) — estrella, CLUSTER BY, valores sin filtro
- [Guía de estilo Looker Studio](looker/STYLE_GUIDE.md) — paleta, contraste AA, páginas y valores esperados

## Disclaimer

Lab de portafolio. Marca con fines ilustrativos. Bronze, silver y gold son sintéticos y el sandbox los borra a los 60 días. Looker Studio se arma a mano con la guía de estilo.

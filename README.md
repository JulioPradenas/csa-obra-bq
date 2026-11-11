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

## Solución (sandbox, por construir)

```text
CSV sintéticos → bronze → silver (y q_<tabla>) → gold → Looker Studio
```

- **Hechos:** `f_avance_partida`, `f_hh_cuadrilla`, `f_consumo_material`.
- **Proyecto GCP:** el de `GCP_PROJECT`. No hay default. El nombre previsto en la Mac es `csa-obra-jp`; este paso no lo crea.
- **Datasets previstos:** `csa_bronze`, `csa_silver`, `csa_gold`. Location `US`.
- **Zona horaria:** `America/Santiago`.
- **Expiración:** 60 días. Sin DML ni streaming. Gold va con `CLUSTER BY`, sin partición por fecha.
- **ERP:** el relato habla de un SAP de obra. No hay conexión.

## Roadmap

| Paso | Entrega | Estado |
|---|---|---|
| 1 | Esqueleto, modelo de datos, guía de estilo | este paso |
| 2 | CSV sintéticos y bronze | pendiente |
| 3 | Silver y cuarentena | pendiente |
| 4 | Gold | pendiente |
| 5 | Looker Studio según la guía | pendiente |

`make test` es lo único que corre hoy. `data`, `bronze`, `silver`, `gold` y `run` ya tienen nombre; los scripts llegan después. En CI, `DRY` parte en 1.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
make test
```

`make test` corre pytest. No llama a BigQuery. La auth del sandbox, cuando exista, es ADC en la Mac de Julio. Este repo no guarda llaves.

## Docs

- [Modelo de datos](docs/modelo-datos.md) — grano, fórmulas, suciedad planeada, sandbox
- [Guía de estilo Looker Studio](looker/STYLE_GUIDE.md) — paleta, contraste AA, páginas en borrador

## Disclaimer

Lab de portafolio. Marca con fines ilustrativos. El Paso 1 no genera datos y no abre GCP.

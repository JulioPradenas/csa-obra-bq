# CSA Obra — lab runners
# Uso: make test | make data | make bronze | make run
#       make run DRY=1
#
# make run en este paso reconstruye el bronze desde cero: CSV, DDL y load
# (CREATE OR REPLACE + WRITE_TRUNCATE, sin DML). verify_bronze imprime
# RESULTADO: OK o RESULTADO: FALLA.
# Silver y gold siguen nombrados; el runner llega en un paso posterior.
#
# Sandbox (sin facturación): sin DML, sin streaming. Las tablas expiran
# a los 60 días; por eso make run no depende de lo que haya quedado de
# la corrida anterior.
#
# Auth: ADC, solo en la Mac de Julio. GCP_PROJECT es obligatorio para
# bronze/run reales (no hay default). DRY=1 no llama a BigQuery.
#
# CI: GitHub Actions deja CI=true. En ese caso DRY parte en 1.
# En la Mac, DRY parte en 0. El workflow además exporta DRY=1.

PY  ?= python3

ifeq ($(CI),true)
  DRY ?= 1
else
  DRY ?= 0
endif

ifeq ($(DRY),1)
  DRY_FLAG := --dry-run
else
  DRY_FLAG :=
endif

.PHONY: help test data bronze silver gold run

help:
	@echo "Targets: data | bronze | silver | gold | run | test"
	@echo "PY=$(PY)  DRY=$(DRY)"
	@echo "GCP_PROJECT debe estar exportado para bronze, silver, gold y run reales (no hay default)."
	@echo "En CI, DRY parte en 1. DRY=1 no consulta BigQuery."

test:
	$(PY) -m pytest -q

data:
	$(PY) scripts/generar_datos.py

bronze:
	$(PY) scripts/apply_ddl.py $(DRY_FLAG)
	$(PY) scripts/load_bronze.py $(DRY_FLAG)

silver:
	@echo "Paso 2: silver llega después. No se llama a BigQuery."
	@exit 1

gold:
	@echo "Paso 2: gold llega después. No se llama a BigQuery."
	@exit 1

run: data bronze
	$(PY) scripts/verify_bronze.py $(DRY_FLAG)

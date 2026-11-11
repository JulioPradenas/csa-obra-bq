# CSA Obra — lab runners
# Uso: make test | make data | make bronze | make run
#       make run DRY=1
#
# make run, cuando existan los scripts, reconstruye todo desde cero:
# CSV, bronze, silver y gold (CREATE OR REPLACE, sin DML). Gold no parte
# por fecha: cluster por obra_id y la segunda clave del hecho.
# verify_bronze imprime OK/FAIL. verify_silver y verify_gold imprimen OK/FALLA.
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

# Paso 1 no trae los scripts. El target ya tiene el nombre del lab de Meli.
# Si el archivo no está, se avisa y se sale: no se inventa un load.
define require_script
	@test -f $(1) || { echo "Paso 1: falta $(1). No se generan datos ni se carga GCP."; exit 1; }
endef

data:
	$(call require_script,scripts/generate_data.py)
	$(PY) scripts/generate_data.py

bronze:
	$(call require_script,scripts/apply_ddl.py)
	$(call require_script,scripts/load_bronze.py)
	$(PY) scripts/apply_ddl.py $(DRY_FLAG)
	$(PY) scripts/load_bronze.py $(DRY_FLAG)

silver:
	$(call require_script,scripts/build_silver.py)
	$(PY) scripts/build_silver.py $(DRY_FLAG)

gold:
	$(call require_script,scripts/build_gold.py)
	$(PY) scripts/build_gold.py $(DRY_FLAG)

run: data bronze silver gold
	$(call require_script,scripts/verify_bronze.py)
	$(call require_script,scripts/verify_silver.py)
	$(call require_script,scripts/verify_gold.py)
	$(PY) scripts/verify_bronze.py $(DRY_FLAG)
	$(PY) scripts/verify_silver.py $(DRY_FLAG)
	$(PY) scripts/verify_gold.py $(DRY_FLAG)

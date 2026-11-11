#!/usr/bin/env python3
"""
CSV sintéticos del lab de obra vial. Semilla fija. No llama a BigQuery.

El núcleo limpio no se muta. La suciedad entra como filas extra, cada una con
un solo problema, más una fila de obras que trae cast y PK vacía a la vez:
el motivo ganador tiene que ser cast_fallido.

Uso:
  python scripts/generar_datos.py
  python scripts/generar_datos.py --seed 42
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from bq_env import DATASET, EXPIRATION_DAYS, LOCATION, NOTICE, ROOT
from contrato import MOTIVOS, PRIORIDAD, TABLE_ORDER, columns
from csv_io import write_table
from motivos import clasificar, contar

SEED = 42
INICIO = date(2026, 5, 4)
TERMINO = date(2026, 11, 27)
HORIZONTE_FIN = date(2026, 9, 21)
# Las 21 semanas del extracto son el 80% de la cantidad de contrato.
# El resto del contrato queda después del corte, hasta fecha_termino.
FRACCION_PROGRAMA = Decimal("0.80")
RAW_DIR = ROOT / "data" / "raw"
MANIFEST_PATH = ROOT / "data" / "manifest.json"

# ratio de ejecución semanal. SPI = este número, porque todas las partidas
# de la obra usan el mismo factor y el precio se cancela en SUM/SUM.
RATIOS = {
    "OBR-01": Decimal("0.70"),
    "OBR-02": Decimal("1.05"),
    "OBR-03": Decimal("0.92"),
    "OBR-04": Decimal("1.00"),
    "OBR-05": Decimal("0.98"),
    "OBR-06": Decimal("0.55"),
    "OBR-07": Decimal("1.00"),
}

OBRAS = (
    {
        "obra_id": "OBR-01",
        "obra_nombre": "Reposición calzada Los Batros",
        "comuna": "San Pedro de la Paz",
        "mandante": "Mandante Sur SpA",
        "tipo_obra": "pavimentacion",
        "estado_obra": "en_ejecucion",
    },
    {
        "obra_id": "OBR-02",
        "obra_nombre": "Conservación costanera Talcahuano",
        "comuna": "Talcahuano",
        "mandante": "Mandante Costa SpA",
        "tipo_obra": "conservacion",
        "estado_obra": "en_ejecucion",
    },
    {
        "obra_id": "OBR-03",
        "obra_nombre": "Puente estero Nonguén",
        "comuna": "Concepción",
        "mandante": "Mandante Puentes SpA",
        "tipo_obra": "puente",
        "estado_obra": "en_ejecucion",
    },
    {
        "obra_id": "OBR-04",
        "obra_nombre": "Colector Michaihue",
        "comuna": "Chiguayante",
        "mandante": "Mandante Lluvia SpA",
        "tipo_obra": "aguas_lluvia",
        "estado_obra": "en_ejecucion",
    },
    {
        "obra_id": "OBR-05",
        "obra_nombre": "Reposición acceso Coronel",
        "comuna": "Coronel",
        "mandante": "Mandante Sur SpA",
        "tipo_obra": "pavimentacion",
        "estado_obra": "en_ejecucion",
    },
    {
        "obra_id": "OBR-06",
        "obra_nombre": "Conservación ruta Hualpén",
        "comuna": "Hualpén",
        "mandante": "Mandante Costa SpA",
        "tipo_obra": "conservacion",
        "estado_obra": "paralizada",
    },
    {
        "obra_id": "OBR-07",
        "obra_nombre": "Mejoramiento bypass Los Ángeles",
        "comuna": "Los Ángeles",
        "mandante": "Mandante Interior SpA",
        "tipo_obra": "pavimentacion",
        "estado_obra": "en_ejecucion",
    },
)

# codigo, nombre, capítulo, unidad, precio CLP, HH teórica (vacío = sin APU).
PLANTILLAS: dict[str, tuple[tuple[str, str, str, str, str, str], ...]] = {
    "pavimentacion": (
        ("1.01", "Excavación en corte", "movimiento_tierras", "m3", "8500", "0.80"),
        ("2.01", "Base granular", "pavimentos", "m3", "22000", "0.45"),
        ("2.03", "Carpeta asfáltica", "pavimentos", "ton", "95000", "1.20"),
        ("3.01", "Cuneta revestida", "drenaje", "ml", "28000", "0.60"),
        ("4.02", "Demarcación de eje", "senalizacion", "m2", "4500", ""),
    ),
    "conservacion": (
        ("1.01", "Escarpe y perfilado", "movimiento_tierras", "m3", "6500", "0.50"),
        ("2.02", "Bacheo asfáltico", "pavimentos", "ton", "88000", "1.10"),
        ("2.04", "Riego de liga", "pavimentos", "m2", "3200", "0.15"),
        ("3.01", "Limpieza de cuneta", "drenaje", "ml", "4200", "0.20"),
        ("4.02", "Reposición de demarcación", "senalizacion", "m2", "4500", ""),
    ),
    "puente": (
        ("1.01", "Excavación de estribo", "movimiento_tierras", "m3", "12000", "0.90"),
        ("5.01", "Hormigón de estribo", "obras_arte", "m3", "180000", "4.50"),
        ("5.02", "Enfierradura", "obras_arte", "kg", "1200", "0.08"),
        ("3.01", "Cuneta de acceso", "drenaje", "ml", "28000", "0.60"),
        ("4.01", "Señalización de obra", "senalizacion", "un", "35000", ""),
    ),
    "aguas_lluvia": (
        ("1.01", "Excavación de zanja", "movimiento_tierras", "m3", "9000", "0.70"),
        ("3.02", "Colector de aguas lluvia", "drenaje", "ml", "64000", "1.50"),
        ("3.03", "Cámara de inspección", "drenaje", "un", "420000", "6.00"),
        ("2.01", "Reposición de base", "pavimentos", "m3", "22000", "0.45"),
        ("4.02", "Demarcación de reposición", "senalizacion", "m2", "4500", ""),
    ),
}

# especialidad de la segunda cuadrilla y el código de partida que se lleva el día.
SEGUNDA = {
    "pavimentacion": ("pavimento", "2.03"),
    "conservacion": ("pavimento", "2.02"),
    "puente": ("estructuras", "5.01"),
    "aguas_lluvia": ("pavimento", "2.01"),
}

PROVEEDORES = (
    ("PRV-CEM", "Cementos del Biobío", "cemento", "Talcahuano"),
    ("PRV-ARI", "Áridos Nonguén", "arido", "Concepción"),
    ("PRV-ASF", "Asfaltos del Sur", "asfalto", "San Pedro de la Paz"),
    ("PRV-ACE", "Aceros Andalién", "acero", "Hualpén"),
    ("PRV-COM", "Combustibles Costanera", "combustible", "Coronel"),
)

MATERIALES = (
    ("MAT-CEM", "Cemento especial", "cemento", "kg", "180", "PRV-CEM"),
    ("MAT-ARI", "Árido base", "arido", "m3", "15000", "PRV-ARI"),
    ("MAT-ASF", "Cemento asfáltico", "asfalto", "ton", "420000", "PRV-ASF"),
    ("MAT-EML", "Emulsión asfáltica", "asfalto", "ton", "380000", "PRV-ASF"),
    ("MAT-ACE", "Acero A630", "acero", "kg", "1100", "PRV-ACE"),
    ("MAT-COM", "Petróleo diésel", "combustible", "l", "1200", "PRV-COM"),
)

# El sobreconsumo visible: asfalto de la reposición de Coronel, +40%.
OBRA_SOBRE = "OBR-05"
MATERIAL_SOBRE = "MAT-ASF"
FACTOR_SOBRE = Decimal("1.40")
PARTIDA_SOBRE_CODIGO = "2.03"


@dataclass(frozen=True)
class Bundle:
    tables: dict[str, list[dict[str, str]]]
    manifest: dict


def lunes_del_horizonte() -> list[date]:
    dias: list[date] = []
    cursor = INICIO
    while cursor <= HORIZONTE_FIN:
        if cursor.weekday() != 0:
            raise RuntimeError(f"{cursor} no es lunes")
        dias.append(cursor)
        cursor += timedelta(days=7)
    return dias


def q2(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")


def fila(table: str, **valores: str) -> dict[str, str]:
    base = {col: "" for col in columns(table)}
    desconocidas = set(valores) - set(base)
    if desconocidas:
        raise KeyError(f"{table}: columnas desconocidas {sorted(desconocidas)}")
    base.update(valores)
    return base


def _fechas_obra() -> dict[str, str]:
    return {
        "fecha_inicio": INICIO.isoformat(),
        "fecha_termino": TERMINO.isoformat(),
        "activo": "true",
    }


def _construir_limpio(
    rng: random.Random,
) -> tuple[dict[str, list[dict[str, str]]], dict[str, str]]:
    """Devuelve tablas limpias y el mapa partida_id de la carpeta de OBR-05."""
    semanas = lunes_del_horizonte()
    tables: dict[str, list[dict[str, str]]] = {table: [] for table in TABLE_ORDER}
    fechas = _fechas_obra()

    for obra in OBRAS:
        tables["obras"].append(fila("obras", **obra, **fechas))

    for proveedor in PROVEEDORES:
        pid, nombre, rubro, comuna = proveedor
        tables["proveedores"].append(
            fila(
                "proveedores",
                proveedor_id=pid,
                proveedor_nombre=nombre,
                rubro=rubro,
                comuna=comuna,
                activo="true",
            )
        )

    for material in MATERIALES:
        mid, nombre, familia, unidad, precio, proveedor = material
        tables["materiales"].append(
            fila(
                "materiales",
                material_id=mid,
                material_nombre=nombre,
                familia=familia,
                unidad_medida=unidad,
                precio_unitario=precio,
                proveedor_id=proveedor,
            )
        )

    partida_de: dict[tuple[str, str], str] = {}
    bases: dict[str, Decimal] = {}
    for obra in OBRAS:
        oid = obra["obra_id"]
        for plantilla in PLANTILLAS[obra["tipo_obra"]]:
            codigo, nombre, capitulo, unidad, precio, hh = plantilla
            pid = f"PAR-{oid[-2:]}-{codigo.replace('.', '')}"
            base = Decimal(100 * rng.randint(1, 3))
            bases[pid] = base
            contrato = base * len(semanas) / FRACCION_PROGRAMA
            tables["partidas"].append(
                fila(
                    "partidas",
                    partida_id=pid,
                    obra_id=oid,
                    codigo_partida=codigo,
                    partida_nombre=nombre,
                    capitulo=capitulo,
                    unidad_medida=unidad,
                    cantidad_contrato=q2(contrato),
                    precio_unitario=precio,
                    hh_teorica_por_unidad=hh,
                )
            )
            partida_de[(oid, codigo)] = pid

    cuadrilla_de: dict[tuple[str, str], str] = {}
    for obra in OBRAS:
        oid = obra["obra_id"]
        tipo = obra["tipo_obra"]
        pares = (("tierras", "1.01"), SEGUNDA[tipo])
        for especialidad, codigo in pares:
            sufijo = especialidad[0].upper()
            cid = f"CUA-{oid[-2:]}-{sufijo}"
            tables["cuadrillas"].append(
                fila(
                    "cuadrillas",
                    cuadrilla_id=cid,
                    cuadrilla_nombre=f"Cuadrilla {especialidad} {oid[-2:]}",
                    especialidad=especialidad,
                    obra_id=oid,
                    activo="true",
                )
            )
            cuadrilla_de[(oid, especialidad)] = cid

    n_prg = 0
    n_med = 0
    for obra in OBRAS:
        oid = obra["obra_id"]
        ratio = RATIOS[oid]
        for plantilla in PLANTILLAS[obra["tipo_obra"]]:
            codigo = plantilla[0]
            pid = partida_de[(oid, codigo)]
            base = bases[pid]
            for semana in semanas:
                n_prg += 1
                n_med += 1
                tables["programa_avance"].append(
                    fila(
                        "programa_avance",
                        programa_id=f"PRG-{n_prg:05d}",
                        obra_id=oid,
                        partida_id=pid,
                        semana_lunes=semana.isoformat(),
                        cantidad_programada=q2(base),
                    )
                )
                tables["medicion_avance"].append(
                    fila(
                        "medicion_avance",
                        medicion_id=f"MED-{n_med:05d}",
                        obra_id=oid,
                        partida_id=pid,
                        semana_lunes=semana.isoformat(),
                        cantidad_ejecutada=q2(base * ratio),
                    )
                )

    n_parte = 0
    for obra in OBRAS:
        oid = obra["obra_id"]
        ratio = RATIOS[oid]
        tipo = obra["tipo_obra"]
        asignaciones = (("tierras", "1.01"), SEGUNDA[tipo])
        for especialidad, codigo in asignaciones:
            cid = cuadrilla_de[(oid, especialidad)]
            pid = partida_de[(oid, codigo)]
            base = bases[pid]
            diario = (base * ratio) / Decimal(5)
            factor = _factor_hh(oid, especialidad)
            for semana in semanas:
                for offset in range(5):
                    n_parte += 1
                    dia = semana + timedelta(days=offset)
                    tables["parte_hh"].append(
                        fila(
                            "parte_hh",
                            parte_id=f"PTE-{n_parte:05d}",
                            obra_id=oid,
                            cuadrilla_id=cid,
                            partida_id=pid,
                            fecha=dia.isoformat(),
                            hh=q2(diario * factor),
                            cantidad_ejecutada=q2(diario),
                        )
                    )

    n_pre = 0
    n_vale = 0
    for obra in OBRAS:
        oid = obra["obra_id"]
        for material in MATERIALES:
            mid = material[0]
            base = Decimal(10 * rng.randint(1, 3))
            factor = FACTOR_SOBRE if oid == OBRA_SOBRE and mid == MATERIAL_SOBRE else Decimal(1)
            for semana in semanas:
                n_pre += 1
                n_vale += 1
                tables["presupuesto_material"].append(
                    fila(
                        "presupuesto_material",
                        presupuesto_id=f"PRE-{n_pre:05d}",
                        obra_id=oid,
                        material_id=mid,
                        semana_lunes=semana.isoformat(),
                        cantidad_presupuestada=q2(base),
                    )
                )
                tables["vale_consumo"].append(
                    fila(
                        "vale_consumo",
                        vale_id=f"VAL-{n_vale:05d}",
                        obra_id=oid,
                        material_id=mid,
                        semana_lunes=semana.isoformat(),
                        cantidad_real=q2(base * factor),
                    )
                )

    carpeta = partida_de[(OBRA_SOBRE, PARTIDA_SOBRE_CODIGO)]
    return tables, {"partida_sobreconsumo": carpeta}


def _factor_hh(obra_id: str, especialidad: str) -> Decimal:
    """HH por unidad del parte. OBR-01 tierras es la cuadrilla lenta."""
    if obra_id == "OBR-01" and especialidad == "tierras":
        return Decimal("1.40")
    if obra_id == "OBR-01":
        return Decimal("1.15")
    return Decimal("0.80")


def _copiar(table: str, tables: dict[str, list[dict[str, str]]]) -> dict[str, str]:
    return dict(tables[table][0])


def _agregar_suciedad(tables: dict[str, list[dict[str, str]]]) -> dict[str, list[str | None]]:
    """Filas extra. El tag es el motivo que la prioridad tiene que devolver."""
    tags: dict[str, list[str | None]] = {
        table: [None] * len(rows) for table, rows in tables.items()
    }
    partida_limpia = tables["partidas"][0]["partida_id"]
    partida_otra = next(
        row["partida_id"]
        for row in tables["partidas"]
        if row["obra_id"] == "OBR-02" and row["codigo_partida"] == "1.01"
    )
    cuadrilla_otra = next(
        row["cuadrilla_id"]
        for row in tables["cuadrillas"]
        if row["obra_id"] == "OBR-02" and row["especialidad"] == "tierras"
    )
    partida_01 = next(
        row["partida_id"]
        for row in tables["partidas"]
        if row["obra_id"] == "OBR-01" and row["codigo_partida"] == "1.01"
    )

    def push(table: str, row: dict[str, str], motivo: str) -> None:
        tables[table].append(row)
        tags[table].append(motivo)

    # --- obras: cast (combo + catálogo), nulo, duplicado, fecha. Sin FK. ---
    push(
        "obras",
        fila(
            "obras",
            obra_id="",
            obra_nombre="Fila con cast y clave vacía",
            comuna="Concepción",
            mandante="Mandante Sur SpA",
            tipo_obra="pavimentacion",
            estado_obra="en_ejecucion",
            fecha_inicio="NO-CAST",
            fecha_termino=TERMINO.isoformat(),
            activo="true",
        ),
        "cast_fallido",
    )
    push(
        "obras",
        fila(
            "obras",
            obra_id="OBR-CAST-TIPO",
            obra_nombre="Obra con tipo fuera de catálogo",
            comuna="Lota",
            mandante="Mandante Sur SpA",
            tipo_obra="demolicion",
            estado_obra="en_ejecucion",
            fecha_inicio=INICIO.isoformat(),
            fecha_termino=TERMINO.isoformat(),
            activo="true",
        ),
        "cast_fallido",
    )
    push(
        "obras",
        fila(
            "obras",
            obra_id="",
            obra_nombre="Obra sin id",
            comuna="Penco",
            mandante="Mandante Sur SpA",
            tipo_obra="conservacion",
            estado_obra="en_ejecucion",
            fecha_inicio=INICIO.isoformat(),
            fecha_termino=TERMINO.isoformat(),
            activo="true",
        ),
        "nulo_obligatorio",
    )
    push("obras", _copiar("obras", tables), "duplicado")
    push(
        "obras",
        fila(
            "obras",
            obra_id="OBR-FECHA",
            obra_nombre="Obra con término anterior al inicio",
            comuna="Tomé",
            mandante="Mandante Costa SpA",
            tipo_obra="conservacion",
            estado_obra="en_ejecucion",
            fecha_inicio=INICIO.isoformat(),
            fecha_termino="2026-04-01",
            activo="true",
        ),
        "fecha_incoherente",
    )

    # --- proveedores ---
    push(
        "proveedores",
        fila(
            "proveedores",
            proveedor_id="PRV-CAST",
            proveedor_nombre="Proveedor con activo ilegible",
            rubro="cemento",
            comuna="Talcahuano",
            activo="SI",
        ),
        "cast_fallido",
    )
    push(
        "proveedores",
        fila(
            "proveedores",
            proveedor_id="",
            proveedor_nombre="Proveedor sin id",
            rubro="arido",
            comuna="Concepción",
            activo="true",
        ),
        "nulo_obligatorio",
    )
    push("proveedores", _copiar("proveedores", tables), "duplicado")

    # --- partidas ---
    push(
        "partidas",
        fila(
            "partidas",
            partida_id="PAR-CAST-PRECIO",
            obra_id="OBR-01",
            codigo_partida="9.99",
            partida_nombre="Partida con precio NO-CAST",
            capitulo="pavimentos",
            unidad_medida="m3",
            cantidad_contrato="100.00",
            precio_unitario="NO-CAST",
            hh_teorica_por_unidad="0.80",
        ),
        "cast_fallido",
    )
    push(
        "partidas",
        fila(
            "partidas",
            partida_id="",
            obra_id="OBR-01",
            codigo_partida="9.98",
            partida_nombre="Partida sin id",
            capitulo="drenaje",
            unidad_medida="ml",
            cantidad_contrato="50.00",
            precio_unitario="1000",
            hh_teorica_por_unidad="0.20",
        ),
        "nulo_obligatorio",
    )
    push("partidas", _copiar("partidas", tables), "duplicado")
    push(
        "partidas",
        fila(
            "partidas",
            partida_id="PAR-FK-01",
            obra_id="OBR-HUERFANA",
            codigo_partida="1.01",
            partida_nombre="Partida de obra que no existe",
            capitulo="movimiento_tierras",
            unidad_medida="m3",
            cantidad_contrato="10.00",
            precio_unitario="8500",
            hh_teorica_por_unidad="0.80",
        ),
        "fk_huerfana",
    )

    # --- cuadrillas ---
    push(
        "cuadrillas",
        fila(
            "cuadrillas",
            cuadrilla_id="CUA-CAST",
            cuadrilla_nombre="Cuadrilla con activo ilegible",
            especialidad="tierras",
            obra_id="OBR-01",
            activo="SI",
        ),
        "cast_fallido",
    )
    push(
        "cuadrillas",
        fila(
            "cuadrillas",
            cuadrilla_id="",
            cuadrilla_nombre="Cuadrilla sin id",
            especialidad="pavimento",
            obra_id="OBR-01",
            activo="true",
        ),
        "nulo_obligatorio",
    )
    push("cuadrillas", _copiar("cuadrillas", tables), "duplicado")
    push(
        "cuadrillas",
        fila(
            "cuadrillas",
            cuadrilla_id="CUA-FK-01",
            cuadrilla_nombre="Cuadrilla de obra que no existe",
            especialidad="tierras",
            obra_id="OBR-HUERFANA",
            activo="true",
        ),
        "fk_huerfana",
    )

    # --- materiales ---
    push(
        "materiales",
        fila(
            "materiales",
            material_id="MAT-CAST",
            material_nombre="Material con precio en coma decimal",
            familia="cemento",
            unidad_medida="kg",
            precio_unitario="12,5",
            proveedor_id="PRV-CEM",
        ),
        "cast_fallido",
    )
    push(
        "materiales",
        fila(
            "materiales",
            material_id="",
            material_nombre="Material sin id",
            familia="acero",
            unidad_medida="kg",
            precio_unitario="1000",
            proveedor_id="PRV-ACE",
        ),
        "nulo_obligatorio",
    )
    push("materiales", _copiar("materiales", tables), "duplicado")
    push(
        "materiales",
        fila(
            "materiales",
            material_id="MAT-FK-01",
            material_nombre="Material de proveedor que no existe",
            familia="combustible",
            unidad_medida="l",
            precio_unitario="900",
            proveedor_id="PRV-HUERFANO",
        ),
        "fk_huerfana",
    )

    # --- programa: cast, nulo, dup, dos FK, dos fechas ---
    push(
        "programa_avance",
        fila(
            "programa_avance",
            programa_id="PRG-CAST",
            obra_id="OBR-01",
            partida_id=partida_01,
            semana_lunes="2026-05-04",
            cantidad_programada="NO-CAST",
        ),
        "cast_fallido",
    )
    push(
        "programa_avance",
        fila(
            "programa_avance",
            programa_id="PRG-NULO",
            obra_id="OBR-01",
            partida_id=partida_01,
            semana_lunes="2026-05-04",
            cantidad_programada="",
        ),
        "nulo_obligatorio",
    )
    push("programa_avance", _copiar("programa_avance", tables), "duplicado")
    push(
        "programa_avance",
        fila(
            "programa_avance",
            programa_id="PRG-FK-1",
            obra_id="OBR-HUERFANA",
            partida_id=partida_limpia,
            semana_lunes="2026-05-11",
            cantidad_programada="10.00",
        ),
        "fk_huerfana",
    )
    push(
        "programa_avance",
        fila(
            "programa_avance",
            programa_id="PRG-FK-2",
            obra_id="OBR-01",
            partida_id=partida_otra,
            semana_lunes="2026-05-04",
            cantidad_programada="10.00",
        ),
        "fk_huerfana",
    )
    push(
        "programa_avance",
        fila(
            "programa_avance",
            programa_id="PRG-FEC-1",
            obra_id="OBR-01",
            partida_id=partida_01,
            semana_lunes="2026-05-06",
            cantidad_programada="10.00",
        ),
        "fecha_incoherente",
    )
    push(
        "programa_avance",
        fila(
            "programa_avance",
            programa_id="PRG-FEC-2",
            obra_id="OBR-01",
            partida_id=partida_01,
            semana_lunes="2026-04-06",
            cantidad_programada="10.00",
        ),
        "fecha_incoherente",
    )

    # --- medición ---
    push(
        "medicion_avance",
        fila(
            "medicion_avance",
            medicion_id="MED-CAST",
            obra_id="OBR-01",
            partida_id=partida_01,
            semana_lunes="2026-02-31",
            cantidad_ejecutada="10.00",
        ),
        "cast_fallido",
    )
    push(
        "medicion_avance",
        fila(
            "medicion_avance",
            medicion_id="MED-NULO",
            obra_id="OBR-02",
            partida_id=partida_otra,
            semana_lunes="2026-05-11",
            cantidad_ejecutada="",
        ),
        "nulo_obligatorio",
    )
    push("medicion_avance", _copiar("medicion_avance", tables), "duplicado")
    push(
        "medicion_avance",
        fila(
            "medicion_avance",
            medicion_id="MED-FK",
            obra_id="OBR-01",
            partida_id="PAR-HUERFANA",
            semana_lunes="2026-05-18",
            cantidad_ejecutada="10.00",
        ),
        "fk_huerfana",
    )
    push(
        "medicion_avance",
        fila(
            "medicion_avance",
            medicion_id="MED-FEC",
            obra_id="OBR-01",
            partida_id=partida_01,
            semana_lunes="2026-05-06",
            cantidad_ejecutada="10.00",
        ),
        "fecha_incoherente",
    )

    # --- parte diario ---
    push(
        "parte_hh",
        fila(
            "parte_hh",
            parte_id="PTE-CAST",
            obra_id="OBR-01",
            cuadrilla_id="CUA-01-T",
            partida_id=partida_01,
            fecha="2026-06-01",
            hh="NO-CAST",
            cantidad_ejecutada="10.00",
        ),
        "cast_fallido",
    )
    push(
        "parte_hh",
        fila(
            "parte_hh",
            parte_id="PTE-NULO",
            obra_id="OBR-01",
            cuadrilla_id="CUA-01-T",
            partida_id=partida_01,
            fecha="2026-08-01",
            hh="",
            cantidad_ejecutada="10.00",
        ),
        "nulo_obligatorio",
    )
    push("parte_hh", _copiar("parte_hh", tables), "duplicado")
    push(
        "parte_hh",
        fila(
            "parte_hh",
            parte_id="PTE-FK-1",
            obra_id="OBR-01",
            cuadrilla_id="CUA-HUERFANA",
            partida_id=partida_01,
            fecha="2026-05-05",
            hh="8.00",
            cantidad_ejecutada="10.00",
        ),
        "fk_huerfana",
    )
    push(
        "parte_hh",
        fila(
            "parte_hh",
            parte_id="PTE-FK-2",
            obra_id="OBR-01",
            cuadrilla_id=cuadrilla_otra,
            partida_id=partida_01,
            fecha="2026-05-04",
            hh="8.00",
            cantidad_ejecutada="10.00",
        ),
        "fk_huerfana",
    )
    push(
        "parte_hh",
        fila(
            "parte_hh",
            parte_id="PTE-FEC",
            obra_id="OBR-01",
            cuadrilla_id="CUA-01-T",
            partida_id=partida_01,
            fecha="2026-04-15",
            hh="8.00",
            cantidad_ejecutada="10.00",
        ),
        "fecha_incoherente",
    )

    # --- presupuesto y vale ---
    push(
        "presupuesto_material",
        fila(
            "presupuesto_material",
            presupuesto_id="PRE-CAST",
            obra_id="OBR-01",
            material_id="MAT-CEM",
            semana_lunes="2026-05-04",
            cantidad_presupuestada="12,5",
        ),
        "cast_fallido",
    )
    push(
        "presupuesto_material",
        fila(
            "presupuesto_material",
            presupuesto_id="PRE-NULO",
            obra_id="OBR-01",
            material_id="MAT-CEM",
            semana_lunes="2026-05-11",
            cantidad_presupuestada="",
        ),
        "nulo_obligatorio",
    )
    push("presupuesto_material", _copiar("presupuesto_material", tables), "duplicado")
    push(
        "presupuesto_material",
        fila(
            "presupuesto_material",
            presupuesto_id="PRE-FK",
            obra_id="OBR-01",
            material_id="MAT-HUERFANA",
            semana_lunes="2026-05-18",
            cantidad_presupuestada="10.00",
        ),
        "fk_huerfana",
    )
    push(
        "presupuesto_material",
        fila(
            "presupuesto_material",
            presupuesto_id="PRE-FEC",
            obra_id="OBR-01",
            material_id="MAT-CEM",
            semana_lunes="2026-11-30",
            cantidad_presupuestada="10.00",
        ),
        "fecha_incoherente",
    )

    push(
        "vale_consumo",
        fila(
            "vale_consumo",
            vale_id="VAL-CAST",
            obra_id="OBR-05",
            material_id="MAT-ASF",
            semana_lunes="2026-05-04",
            cantidad_real="NO-CAST",
        ),
        "cast_fallido",
    )
    push(
        "vale_consumo",
        fila(
            "vale_consumo",
            vale_id="VAL-NULO",
            obra_id="OBR-05",
            material_id="MAT-ASF",
            semana_lunes="2026-05-11",
            cantidad_real="",
        ),
        "nulo_obligatorio",
    )
    push("vale_consumo", _copiar("vale_consumo", tables), "duplicado")
    push(
        "vale_consumo",
        fila(
            "vale_consumo",
            vale_id="VAL-FK",
            obra_id="OBR-HUERFANA",
            material_id="MAT-ASF",
            semana_lunes="2026-05-18",
            cantidad_real="10.00",
        ),
        "fk_huerfana",
    )
    push(
        "vale_consumo",
        fila(
            "vale_consumo",
            vale_id="VAL-FEC",
            obra_id="OBR-05",
            material_id="MAT-EML",
            semana_lunes="2026-05-06",
            cantidad_real="10.00",
        ),
        "fecha_incoherente",
    )
    return tags


def _monto(cantidad: str, precio: str) -> Decimal:
    return Decimal(cantidad) * Decimal(precio)


def _spi(
    tables: dict[str, list[dict[str, str]]],
    motives: dict[str, list[str | None]],
    obra_id: str,
) -> Decimal:
    precio = {
        row["partida_id"]: Decimal(row["precio_unitario"])
        for row, motivo in zip(tables["partidas"], motives["partidas"], strict=True)
        if motivo is None and row["obra_id"] == obra_id
    }
    programado = Decimal(0)
    ejecutado = Decimal(0)
    for row, motivo in zip(tables["programa_avance"], motives["programa_avance"], strict=True):
        if motivo is None and row["obra_id"] == obra_id:
            programado += _monto(row["cantidad_programada"], str(precio[row["partida_id"]]))
    for row, motivo in zip(tables["medicion_avance"], motives["medicion_avance"], strict=True):
        if motivo is None and row["obra_id"] == obra_id:
            ejecutado += _monto(row["cantidad_ejecutada"], str(precio[row["partida_id"]]))
    return ejecutado / programado


def _avance_fisico(
    tables: dict[str, list[dict[str, str]]],
    motives: dict[str, list[str | None]],
    obra_id: str,
) -> Decimal:
    contrato = Decimal(0)
    for row, motivo in zip(tables["partidas"], motives["partidas"], strict=True):
        if motivo is None and row["obra_id"] == obra_id:
            contrato += _monto(row["cantidad_contrato"], row["precio_unitario"])
    ejecutado = Decimal(0)
    precio = {
        row["partida_id"]: row["precio_unitario"]
        for row, motivo in zip(tables["partidas"], motives["partidas"], strict=True)
        if motivo is None
    }
    for row, motivo in zip(tables["medicion_avance"], motives["medicion_avance"], strict=True):
        if motivo is None and row["obra_id"] == obra_id:
            ejecutado += _monto(row["cantidad_ejecutada"], precio[row["partida_id"]])
    return ejecutado / contrato


def _desviacion(
    tables: dict[str, list[dict[str, str]]],
    motives: dict[str, list[str | None]],
    obra_id: str,
    material_id: str,
) -> Decimal:
    precio = {
        row["material_id"]: Decimal(row["precio_unitario"])
        for row, motivo in zip(tables["materiales"], motives["materiales"], strict=True)
        if motivo is None
    }[material_id]
    real = Decimal(0)
    presupuestado = Decimal(0)
    for row, motivo in zip(
        tables["presupuesto_material"], motives["presupuesto_material"], strict=True
    ):
        if motivo is None and row["obra_id"] == obra_id and row["material_id"] == material_id:
            presupuestado += Decimal(row["cantidad_presupuestada"]) * precio
    for row, motivo in zip(tables["vale_consumo"], motives["vale_consumo"], strict=True):
        if motivo is None and row["obra_id"] == obra_id and row["material_id"] == material_id:
            real += Decimal(row["cantidad_real"]) * precio
    return (real - presupuestado) / presupuestado


def _hh_por_unidad(
    tables: dict[str, list[dict[str, str]]],
    motives: dict[str, list[str | None]],
    obra_id: str,
    especialidad: str,
) -> Decimal:
    cuadrillas = {
        row["cuadrilla_id"]
        for row, motivo in zip(tables["cuadrillas"], motives["cuadrillas"], strict=True)
        if motivo is None and row["obra_id"] == obra_id and row["especialidad"] == especialidad
    }
    hh = Decimal(0)
    cantidad = Decimal(0)
    for row, motivo in zip(tables["parte_hh"], motives["parte_hh"], strict=True):
        if motivo is None and row["cuadrilla_id"] in cuadrillas:
            hh += Decimal(row["hh"])
            cantidad += Decimal(row["cantidad_ejecutada"])
    return hh / cantidad


def _manifest(
    seed: int,
    tables: dict[str, list[dict[str, str]]],
    motives: dict[str, list[str | None]],
    partida_sobreconsumo: str,
) -> dict:
    anomalies = contar(motives)
    clean_counts = {
        table: sum(1 for motivo in motives[table] if motivo is None) for table in TABLE_ORDER
    }
    row_counts = {table: len(tables[table]) for table in TABLE_ORDER}
    for table in TABLE_ORDER:
        extra = sum(anomalies[table].values())
        if clean_counts[table] + extra != row_counts[table]:
            raise RuntimeError(f"{table}: clean + suciedad no cuadra con las filas")

    spi_atrasada = _spi(tables, motives, "OBR-01")
    spi_al_dia = _spi(tables, motives, "OBR-02")
    spi_paralizada = _spi(tables, motives, "OBR-06")
    avance_atrasada = _avance_fisico(tables, motives, "OBR-01")
    avance_al_dia = _avance_fisico(tables, motives, "OBR-02")
    desviacion = _desviacion(tables, motives, OBRA_SOBRE, MATERIAL_SOBRE)
    hh_lenta = _hh_por_unidad(tables, motives, "OBR-01", "tierras")
    hh_al_dia = _hh_por_unidad(tables, motives, "OBR-02", "tierras")

    if spi_atrasada != RATIOS["OBR-01"] or spi_al_dia != RATIOS["OBR-02"]:
        raise RuntimeError(f"SPI inesperado: {spi_atrasada} / {spi_al_dia}")
    if desviacion != (FACTOR_SOBRE - 1):
        raise RuntimeError(f"desviación inesperada: {desviacion}")
    if hh_lenta != Decimal("1.40") or hh_al_dia != Decimal("0.80"):
        raise RuntimeError(f"HH por unidad inesperado: {hh_lenta} / {hh_al_dia}")

    obra = {row["obra_id"]: row for row in tables["obras"]}
    return {
        "aviso": NOTICE,
        "seed": seed,
        "dataset": DATASET,
        "location": LOCATION,
        "expiration_days": EXPIRATION_DAYS,
        "horizon_start": INICIO.isoformat(),
        "horizon_end": HORIZONTE_FIN.isoformat(),
        "fecha_inicio_obras": INICIO.isoformat(),
        "fecha_termino_obras": TERMINO.isoformat(),
        "fraccion_programa_en_el_horizonte": "0.80",
        "prioridad": PRIORIDAD,
        "motivos": list(MOTIVOS),
        "clean_counts": clean_counts,
        "row_counts": row_counts,
        "anomalies": anomalies,
        "historia": {
            "obra_atrasada": {
                "obra_id": "OBR-01",
                "obra_nombre": obra["OBR-01"]["obra_nombre"],
                "comuna": obra["OBR-01"]["comuna"],
                "estado_obra": obra["OBR-01"]["estado_obra"],
                "spi": q2(spi_atrasada),
                "avance_fisico_al_corte": q2(avance_atrasada),
            },
            "obra_al_dia": {
                "obra_id": "OBR-02",
                "obra_nombre": obra["OBR-02"]["obra_nombre"],
                "comuna": obra["OBR-02"]["comuna"],
                "spi": q2(spi_al_dia),
                "avance_fisico_al_corte": q2(avance_al_dia),
            },
            "obra_paralizada": {
                "obra_id": "OBR-06",
                "obra_nombre": obra["OBR-06"]["obra_nombre"],
                "comuna": obra["OBR-06"]["comuna"],
                "estado_obra": "paralizada",
                "spi": q2(spi_paralizada),
            },
            "sobreconsumo": {
                "obra_id": OBRA_SOBRE,
                "obra_nombre": obra[OBRA_SOBRE]["obra_nombre"],
                "partida_id": partida_sobreconsumo,
                "partida_nombre": "Carpeta asfáltica",
                "material_id": MATERIAL_SOBRE,
                "material_nombre": "Cemento asfáltico",
                "desviacion": q2(desviacion),
                "nota": (
                    "El vale es obra × material × semana. El residente atribuye "
                    "el asfalto de más a la carpeta de esta obra; el grano no prorratea."
                ),
            },
            "hh_tierras": {
                "lenta": {"obra_id": "OBR-01", "hh_por_unidad": q2(hh_lenta)},
                "al_dia": {"obra_id": "OBR-02", "hh_por_unidad": q2(hh_al_dia)},
            },
        },
        "prioridad_demo": {
            "tabla": "obras",
            "obra_nombre": "Fila con cast y clave vacía",
            "motivo": "cast_fallido",
            "nota": "fecha_inicio=NO-CAST y obra_id vacío. Gana el cast.",
        },
        "nota": (
            "row_counts es el total bronze (lo que num_rows tiene que igualar). "
            "anomalies cuenta filas extra por el motivo ganador. "
            "row_counts = clean_counts + suma de anomalies. "
            "clean_counts es lo que queda en silver si la prioridad se aplica igual. "
            "Los ceros también van, para que no haya un motivo olvidado."
        ),
    }


def _exigir_tags(
    tables: dict[str, list[dict[str, str]]],
    tags: dict[str, list[str | None]],
    motives: dict[str, list[str | None]],
) -> None:
    for table in TABLE_ORDER:
        if tags[table] == motives[table]:
            continue
        for index, (esperado, obtenido) in enumerate(
            zip(tags[table], motives[table], strict=True)
        ):
            if esperado != obtenido:
                raise SystemExit(
                    f"Suciedad mal clasificada en {table} fila {index}: "
                    f"esperado={esperado} obtenido={obtenido} row={tables[table][index]}"
                )
        raise SystemExit(f"Largo distinto de tags en {table}")


def generate(seed: int = SEED) -> Bundle:
    rng = random.Random(seed)
    tables, extra = _construir_limpio(rng)
    tags = _agregar_suciedad(tables)
    motives = clasificar(tables)
    _exigir_tags(tables, tags, motives)
    manifest = _manifest(seed, tables, motives, extra["partida_sobreconsumo"])
    return Bundle(tables=tables, manifest=manifest)


def write_outputs(
    bundle: Bundle,
    raw_dir: Path = RAW_DIR,
    manifest_path: Path = MANIFEST_PATH,
) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    for table in TABLE_ORDER:
        write_table(raw_dir / f"{table}.csv", table, bundle.tables[table])
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(bundle.manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Genera CSV sintéticos y data/manifest.json.")
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args(argv)
    bundle = generate(args.seed)
    write_outputs(bundle)
    print(f"seed={args.seed}")
    print(f"raw_dir={RAW_DIR}")
    print(f"manifest={MANIFEST_PATH}")
    for table in TABLE_ORDER:
        print(f"  {table:<22} {bundle.manifest['row_counts'][table]:6d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

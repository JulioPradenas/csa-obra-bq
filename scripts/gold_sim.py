"""Estrella gold en memoria, con las mismas reglas que sql/gold.

Lee el silver que deja la cuarentena (motivo None). No llama a BigQuery.
Los KPI salen de sumas: no se promedia un porcentaje guardado en la fila.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from contrato import TABLE_ORDER
from motivos import clasificar

UNIDAD_NOMBRE = {
    "m3": "m³",
    "m2": "m²",
    "ml": "ml",
    "kg": "kg",
    "ton": "t",
    "l": "L",
    "un": "un",
}

MESES = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)
DIAS = (
    "lunes",
    "martes",
    "miércoles",
    "jueves",
    "viernes",
    "sábado",
    "domingo",
)

GOLD_ORDER = (
    "d_obra",
    "d_proveedor",
    "d_partida",
    "d_cuadrilla",
    "d_material",
    "d_fecha",
    "f_avance_partida",
    "f_hh_cuadrilla",
    "f_consumo_material",
)


def _d(value: str) -> Decimal:
    return Decimal(value)


def _fecha(value: str) -> date:
    return date.fromisoformat(value)


def silver_limpio(
    tables: dict[str, list[dict[str, str]]],
    motives: dict[str, list[str | None]] | None = None,
) -> dict[str, list[dict[str, str]]]:
    labels = motives if motives is not None else clasificar(tables)
    return {
        table: [row for row, motivo in zip(tables[table], labels[table], strict=True) if motivo is None]
        for table in TABLE_ORDER
    }


def _index(rows: list[dict[str, str]], key: str) -> dict[str, dict[str, str]]:
    return {row[key]: row for row in rows}


def build_dims(silver: dict[str, list[dict[str, str]]]) -> dict[str, list[dict]]:
    obras = []
    for row in silver["obras"]:
        obras.append(
            {
                "obra_id": row["obra_id"],
                "obra_nombre": row["obra_nombre"],
                "comuna": row["comuna"],
                "mandante": row["mandante"],
                "tipo_obra": row["tipo_obra"],
                "estado_obra": row["estado_obra"],
                "fecha_inicio": _fecha(row["fecha_inicio"]),
                "fecha_termino": _fecha(row["fecha_termino"]),
                "activo": row["activo"] in {"true", "True", "1"},
            }
        )
    proveedores = []
    for row in silver["proveedores"]:
        proveedores.append(
            {
                "proveedor_id": row["proveedor_id"],
                "proveedor_nombre": row["proveedor_nombre"],
                "rubro": row["rubro"],
                "comuna": row["comuna"],
                "activo": row["activo"] in {"true", "True", "1"},
            }
        )
    partidas = []
    for row in silver["partidas"]:
        cantidad = _d(row["cantidad_contrato"])
        precio = _d(row["precio_unitario"])
        hh = row["hh_teorica_por_unidad"].strip()
        partidas.append(
            {
                "partida_id": row["partida_id"],
                "obra_id": row["obra_id"],
                "codigo_partida": row["codigo_partida"],
                "partida_nombre": row["partida_nombre"],
                "capitulo": row["capitulo"],
                "unidad_medida": row["unidad_medida"],
                "unidad_nombre": UNIDAD_NOMBRE[row["unidad_medida"]],
                "cantidad_contrato": cantidad,
                "precio_unitario": precio,
                "monto_contrato": cantidad * precio,
                "hh_teorica_por_unidad": _d(hh) if hh else None,
            }
        )
    cuadrillas = []
    for row in silver["cuadrillas"]:
        cuadrillas.append(
            {
                "cuadrilla_id": row["cuadrilla_id"],
                "cuadrilla_nombre": row["cuadrilla_nombre"],
                "especialidad": row["especialidad"],
                "obra_id": row["obra_id"],
                "activo": row["activo"] in {"true", "True", "1"},
            }
        )
    materiales = []
    for row in silver["materiales"]:
        materiales.append(
            {
                "material_id": row["material_id"],
                "material_nombre": row["material_nombre"],
                "familia": row["familia"],
                "unidad_medida": row["unidad_medida"],
                "unidad_nombre": UNIDAD_NOMBRE[row["unidad_medida"]],
                "precio_unitario": _d(row["precio_unitario"]),
                "proveedor_id": row["proveedor_id"],
            }
        )
    if not obras:
        fechas: list[dict] = []
    else:
        inicio = min(row["fecha_inicio"] for row in obras)
        termino = max(row["fecha_termino"] for row in obras)
        fechas = []
        cursor = inicio
        while cursor <= termino:
            fechas.append(
                {
                    "fecha": cursor,
                    "anio": cursor.year,
                    "mes": cursor.month,
                    "mes_nombre": MESES[cursor.month - 1],
                    "semana_iso": cursor.isocalendar()[1],
                    "lunes_semana": cursor - timedelta(days=cursor.weekday()),
                    "nombre_dia": DIAS[cursor.weekday()],
                    "es_fin_de_semana": cursor.weekday() >= 5,
                }
            )
            cursor += timedelta(days=1)
    return {
        "d_obra": obras,
        "d_proveedor": proveedores,
        "d_partida": partidas,
        "d_cuadrilla": cuadrillas,
        "d_material": materiales,
        "d_fecha": fechas,
    }


def build_hechos(
    silver: dict[str, list[dict[str, str]]],
    dims: dict[str, list[dict]],
) -> dict[str, list[dict]]:
    precio_partida = {row["partida_id"]: row["precio_unitario"] for row in dims["d_partida"]}
    precio_material = {row["material_id"]: row["precio_unitario"] for row in dims["d_material"]}

    programado: dict[tuple[str, str, str], Decimal] = {}
    for row in silver["programa_avance"]:
        key = (row["obra_id"], row["partida_id"], row["semana_lunes"])
        programado[key] = _d(row["cantidad_programada"])
    ejecutado: dict[tuple[str, str, str], Decimal] = {}
    for row in silver["medicion_avance"]:
        key = (row["obra_id"], row["partida_id"], row["semana_lunes"])
        ejecutado[key] = _d(row["cantidad_ejecutada"])

    avance = []
    for obra_id, partida_id, semana in sorted(set(programado) | set(ejecutado)):
        cantidad_programada = programado.get((obra_id, partida_id, semana), Decimal(0))
        cantidad_ejecutada = ejecutado.get((obra_id, partida_id, semana), Decimal(0))
        precio = precio_partida[partida_id]
        avance.append(
            {
                "obra_id": obra_id,
                "partida_id": partida_id,
                "semana_lunes": _fecha(semana),
                "cantidad_programada": cantidad_programada,
                "cantidad_ejecutada": cantidad_ejecutada,
                "precio_unitario": precio,
                "monto_programado": cantidad_programada * precio,
                "monto_ejecutado": cantidad_ejecutada * precio,
            }
        )

    hh = []
    for row in silver["parte_hh"]:
        hh.append(
            {
                "obra_id": row["obra_id"],
                "cuadrilla_id": row["cuadrilla_id"],
                "partida_id": row["partida_id"],
                "fecha": _fecha(row["fecha"]),
                "hh": _d(row["hh"]),
                "cantidad_ejecutada": _d(row["cantidad_ejecutada"]),
            }
        )

    presupuestado: dict[tuple[str, str, str], Decimal] = {}
    for row in silver["presupuesto_material"]:
        key = (row["obra_id"], row["material_id"], row["semana_lunes"])
        presupuestado[key] = _d(row["cantidad_presupuestada"])
    real: dict[tuple[str, str, str], Decimal] = {}
    for row in silver["vale_consumo"]:
        key = (row["obra_id"], row["material_id"], row["semana_lunes"])
        real[key] = _d(row["cantidad_real"])
    consumo = []
    for obra_id, material_id, semana in sorted(set(presupuestado) | set(real)):
        cantidad_presupuestada = presupuestado.get((obra_id, material_id, semana), Decimal(0))
        cantidad_real = real.get((obra_id, material_id, semana), Decimal(0))
        precio = precio_material[material_id]
        consumo.append(
            {
                "obra_id": obra_id,
                "material_id": material_id,
                "semana_lunes": _fecha(semana),
                "cantidad_presupuestada": cantidad_presupuestada,
                "cantidad_real": cantidad_real,
                "precio_unitario": precio,
                "monto_presupuestado": cantidad_presupuestada * precio,
                "monto_real": cantidad_real * precio,
            }
        )
    return {
        "f_avance_partida": avance,
        "f_hh_cuadrilla": hh,
        "f_consumo_material": consumo,
    }


def huerfanas(dims: dict[str, list[dict]], hechos: dict[str, list[dict]]) -> int:
    obras = {row["obra_id"] for row in dims["d_obra"]}
    partidas = {row["partida_id"]: row["obra_id"] for row in dims["d_partida"]}
    cuadrillas = {row["cuadrilla_id"]: row["obra_id"] for row in dims["d_cuadrilla"]}
    materiales = {row["material_id"] for row in dims["d_material"]}
    proveedores = {row["proveedor_id"] for row in dims["d_proveedor"]}
    rotas = 0
    for row in dims["d_partida"]:
        if row["obra_id"] not in obras:
            rotas += 1
    for row in dims["d_cuadrilla"]:
        if row["obra_id"] not in obras:
            rotas += 1
    for row in dims["d_material"]:
        if row["proveedor_id"] not in proveedores:
            rotas += 1
    for row in hechos["f_avance_partida"]:
        if row["obra_id"] not in obras or partidas.get(row["partida_id"]) != row["obra_id"]:
            rotas += 1
    for row in hechos["f_hh_cuadrilla"]:
        if (
            row["obra_id"] not in obras
            or cuadrillas.get(row["cuadrilla_id"]) != row["obra_id"]
            or partidas.get(row["partida_id"]) != row["obra_id"]
        ):
            rotas += 1
    for row in hechos["f_consumo_material"]:
        if row["obra_id"] not in obras or row["material_id"] not in materiales:
            rotas += 1
    return rotas


def _suma(rows: list[dict], column: str, obra_id: str | None = None, **filtros: str) -> Decimal:
    total = Decimal(0)
    for row in rows:
        if obra_id is not None and row.get("obra_id") != obra_id:
            continue
        if any(row.get(key) != value for key, value in filtros.items()):
            continue
        total += row[column]
    return total


def kpis(dims: dict[str, list[dict]], hechos: dict[str, list[dict]]) -> dict[str, Decimal | None]:
    avance = hechos["f_avance_partida"]
    consumo = hechos["f_consumo_material"]
    hh = hechos["f_hh_cuadrilla"]
    contrato = sum((row["monto_contrato"] for row in dims["d_partida"]), Decimal(0))
    ejec = _suma(avance, "monto_ejecutado")
    prog = _suma(avance, "monto_programado")
    real = _suma(consumo, "monto_real")
    presup = _suma(consumo, "monto_presupuestado")

    def spi(obra_id: str) -> Decimal:
        return _suma(avance, "monto_ejecutado", obra_id) / _suma(avance, "monto_programado", obra_id)

    def avance_fisico(obra_id: str) -> Decimal:
        contrato_obra = sum(
            (row["monto_contrato"] for row in dims["d_partida"] if row["obra_id"] == obra_id),
            Decimal(0),
        )
        return _suma(avance, "monto_ejecutado", obra_id) / contrato_obra

    def desviacion(obra_id: str, material_id: str) -> Decimal:
        real_m = _suma(consumo, "monto_real", obra_id, material_id=material_id)
        presup_m = _suma(consumo, "monto_presupuestado", obra_id, material_id=material_id)
        return (real_m - presup_m) / presup_m

    cuadrillas = {row["cuadrilla_id"]: row for row in dims["d_cuadrilla"]}

    def hh_unidad(obra_id: str, especialidad: str) -> Decimal:
        ids = {
            row["cuadrilla_id"]
            for row in dims["d_cuadrilla"]
            if row["obra_id"] == obra_id and row["especialidad"] == especialidad
        }
        horas = Decimal(0)
        cantidad = Decimal(0)
        for row in hh:
            if row["cuadrilla_id"] in ids:
                horas += row["hh"]
                cantidad += row["cantidad_ejecutada"]
        return horas / cantidad

    del cuadrillas
    return {
        "monto_ejecutado": ejec,
        "monto_programado": prog,
        "monto_contrato": contrato,
        "spi": ejec / prog,
        "avance_fisico": ejec / contrato,
        "monto_real": real,
        "monto_presupuestado": presup,
        "desviacion": (real - presup) / presup,
        "hh": sum((row["hh"] for row in hh), Decimal(0)),
        "spi_obr_01": spi("OBR-01"),
        "avance_obr_01": avance_fisico("OBR-01"),
        "spi_obr_02": spi("OBR-02"),
        "avance_obr_02": avance_fisico("OBR-02"),
        "spi_obr_06": spi("OBR-06"),
        "desviacion_asfalto_coronel": desviacion("OBR-05", "MAT-ASF"),
        "hh_tierras_obr_01": hh_unidad("OBR-01", "tierras"),
        "hh_tierras_obr_02": hh_unidad("OBR-02", "tierras"),
    }


def simular(tables: dict[str, list[dict[str, str]]]) -> dict:
    motives = clasificar(tables)
    silver = silver_limpio(tables, motives)
    dims = build_dims(silver)
    hechos = build_hechos(silver, dims)
    tablas = {**dims, **hechos}
    conteos = {nombre: len(filas) for nombre, filas in tablas.items()}
    conteos_silver = {
        "programa_avance": len(silver["programa_avance"]),
        "medicion_avance": len(silver["medicion_avance"]),
        "parte_hh": len(silver["parte_hh"]),
        "presupuesto_material": len(silver["presupuesto_material"]),
        "vale_consumo": len(silver["vale_consumo"]),
    }
    return {
        "conteos": conteos,
        "conteos_silver": conteos_silver,
        "kpis": kpis(dims, hechos),
        "huerfanas": huerfanas(dims, hechos),
        "dims": dims,
        "hechos": hechos,
    }


def q2(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")

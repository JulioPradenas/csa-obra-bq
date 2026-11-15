# Paso 5 — Vistas para Looker Studio

> **Lab de portafolio. Marca con fines ilustrativos.**

Looker Studio trabaja mejor con una fuente plana por página. Gold es una estrella, así que este paso agrega tres vistas en `csa_gold` (sin DML, `CREATE OR REPLACE VIEW`):

| Vista | Páginas | Grano |
|---|---|---|
| `v_avance_semana` | Resumen de obras, Avance vs programa | obra × partida × semana |
| `v_hh_dia` | Productividad HH | obra × cuadrilla × día |
| `v_consumo_semana` | Materiales y desviación | obra × material × semana |

Las vistas traen los nombres legibles (estado, capítulo, familia, etiqueta de cuadrilla) para que el informe no necesite campos `CASE`.

## El contrato una vez por partida

El % avance físico divide por `monto_contrato`, que vive en `d_partida`. En `v_avance_semana` el monto de contrato va solo en la **primera semana** de cada partida y en las demás es 0. Así `SUM(monto_contrato)` lo cuenta una vez. Regla de uso: el control de período de esas páginas siempre parte en la primera semana (04/05/2026); solo se mueve la fecha de corte. Es la misma definición de la guía de estilo: el acumulado suma desde el inicio hasta la semana de corte.

## Correrlo en la Mac

```bash
export GCP_PROJECT=csa-obra-jp
make looker
```

`make run` también lo corre al final. El script crea las vistas y compara contra los valores sin filtro de gold: 735 / 1.470 / 882 filas, SPI 0,8978, % avance 0,7183, desviación 0,0455, `SUM(hh)` 42.707,70 y HH por m³ de las cuadrillas de tierras 0,9101. Termina en `RESULTADO: OK` o `RESULTADO: FALLA`.

"""Paso 1 — el modelo, la guía y el esqueleto que el CI verifica."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AVISO = "Lab de portafolio. Marca con fines ilustrativos."

README = ROOT / "README.md"
MODELO = ROOT / "docs" / "modelo-datos.md"
GUIA = ROOT / "looker" / "STYLE_GUIDE.md"

PALETA = ("#FED501", "#1F5C3F", "#2E7D57", "#333333")

FORMULAS = (
    "% avance físico = SUM(monto_ejecutado) / SUM(monto_contrato)",
    "SPI = SUM(monto_ejecutado) / SUM(monto_programado)",
    "HH por unidad ejecutada = SUM(hh) / SUM(cantidad_ejecutada)",
    "desviación de consumo = (SUM(monto_real) - SUM(monto_presupuestado)) / SUM(monto_presupuestado)",
    "nunca como promedio de porcentajes",
)

GRANOS = (
    "f_avance_partida",
    "f_hh_cuadrilla",
    "f_consumo_material",
    "obra × partida × semana",
    "obra × cuadrilla × día",
    "obra × material × semana",
    "d_obra",
    "d_partida",
    "d_cuadrilla",
    "d_material",
    "d_proveedor",
    "d_fecha",
)

MOTIVOS = (
    "cast_fallido > nulo_obligatorio > duplicado > fk_huerfana > fecha_incoherente",
)


def _texto(path: Path) -> str:
    assert path.is_file(), f"falta {path.relative_to(ROOT)}"
    return path.read_text(encoding="utf-8")


def test_docs_existen():
    for path in (README, MODELO, GUIA):
        assert path.is_file(), path


def test_aviso_en_readme_modelo_y_guia():
    for path in (README, MODELO, GUIA):
        assert AVISO in _texto(path)


def test_guia_tiene_paleta_aviso_y_contraste_aa():
    texto = _texto(GUIA)
    assert AVISO in texto
    for color in PALETA:
        assert color in texto, color
    assert "AA" in texto


def test_modelo_fija_granos_formulas_y_cuarentena():
    texto = _texto(MODELO)
    for pieza in GRANOS + FORMULAS + MOTIVOS:
        assert pieza in texto, pieza
    assert "todo STRING NULLABLE" in texto
    assert "SAFE_CAST" in texto
    assert "q_<tabla>" in texto
    assert "CLUSTER BY" in texto


def test_formulas_tambien_en_la_guia():
    texto = _texto(GUIA)
    for pieza in FORMULAS:
        assert pieza in texto, pieza


def test_esqueleto_de_carpetas():
    for rel in (
        "sql/bronze",
        "sql/silver",
        "sql/gold",
        "scripts",
        "docs",
        "looker",
        "tests",
    ):
        assert (ROOT / rel).is_dir(), rel


def test_makefile_dry_en_ci_y_workflow_pytest():
    makefile = _texto(ROOT / "Makefile")
    assert "pytest" in makefile
    assert "ifeq ($(CI),true)" in makefile
    assert "DRY ?= 1" in makefile
    workflow = _texto(ROOT / ".github" / "workflows" / "pytest.yml")
    assert "push:" in workflow
    assert "pull_request:" in workflow
    assert "make test" in workflow
    assert 'DRY: "1"' in workflow

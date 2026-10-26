"""Pruebas de importación masiva segura desde Excel."""
from io import BytesIO
from decimal import Decimal

import pytest
from openpyxl import Workbook

from agente_comprobantes.control_financiero.importacion_masiva import (
    confirmar_importacion,
    preparar_importacion,
)
from agente_comprobantes.control_financiero.repositorio_json import RepositorioControlFletes

HEADERS = [
    "Nro. Bancarización", "Detracción", "Nro de Guía", "Proveedor",
    "Fecha Factura", "N° Factura", "Moneda", "Monto bancarizado",
    "Monto Facturado", "Estado", "Nota de Crédito",
]


def excel(rows: list[list[object]], title: str = "FLETES Y DETRACCIONES") -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = title
    ws.append(["FLETES Y DETRACCIONES"])
    ws.append(["Registro detallado de operaciones"])
    ws.append([])
    for row in rows:
        ws.append(row)
    out = BytesIO()
    wb.save(out)
    return out.getvalue()


def fila(
    number: str = "F001-12",
    provider: str = "Transportes Sur SAC",
    billed: object = 1000,
    paid: object = 960,
    currency: str = "PEN",
) -> list[object]:
    return [
        "OP-100", "SI", "EG07-52", provider, "2026-09-12",
        number, currency, paid, billed, "Conforme", "No Aplica",
    ]


def test_vista_previa_no_escribe_y_no_acredita(tmp_path) -> None:
    repo = RepositorioControlFletes(tmp_path / "control.json")
    prev = preparar_importacion(excel([HEADERS, fila()]), repo)
    assert prev.nombre_hoja == "FLETES Y DETRACCIONES"
    assert prev.encabezado == 4
    assert len(prev.listas) == 1
    op = prev.listas[0]
    assert op.es_flete is None
    assert op.detraccion_aplica is None
    assert op.movimientos_bancarios[0].importe_aplicado == Decimal("960")
    assert op.movimientos_bancarios[0].verificada is False
    assert op.numero_guia == "EG07-52"
    assert not (tmp_path / "control.json").exists()


def test_importa_lote_y_reimportar_detecta_duplicados(tmp_path) -> None:
    repo = RepositorioControlFletes(tmp_path / "control.json")
    raw = excel([HEADERS, fila(), fila("F001-13", "Transportes Norte", 800, 0)])
    prev = preparar_importacion(raw, repo)
    assert len(prev.listas) == 2
    assert confirmar_importacion(prev, repo) == 2
    assert len(repo.listar()) == 2
    segunda = preparar_importacion(raw, repo)
    assert segunda.duplicadas == 2
    assert not segunda.listas


def test_filas_invalidas_no_impiden_validas(tmp_path) -> None:
    repo = RepositorioControlFletes(tmp_path / "control.json")
    raw = excel([
        HEADERS, fila(),
        fila("F001-14", "Transportes X", -5),
        fila("F001-15", "Transportes Y", 200, 0, "XXX"),
        fila("F001-16", "Transportes Z", 400, 0),
    ])
    prev = preparar_importacion(raw, repo)
    assert prev.errores == 2
    assert len(prev.listas) == 2
    assert confirmar_importacion(prev, repo) == 2


def test_duplicados_en_el_mismo_lote(tmp_path) -> None:
    repo = RepositorioControlFletes(tmp_path / "control.json")
    prev = preparar_importacion(excel([HEADERS, fila(), fila()]), repo)
    assert len(prev.listas) == 1
    assert prev.duplicadas == 1


def test_no_sobrescribe_si_control_cambia_tras_previa(tmp_path) -> None:
    repo = RepositorioControlFletes(tmp_path / "control.json")
    prev = preparar_importacion(excel([HEADERS, fila()]), repo)
    otro = preparar_importacion(
        excel([HEADERS, fila("F009-99", "Transportes O", 400, 0)]), repo
    )
    confirmar_importacion(otro, repo)
    antes = (tmp_path / "control.json").read_bytes()
    with pytest.raises(ValueError, match="cambió"):
        confirmar_importacion(prev, repo)
    assert (tmp_path / "control.json").read_bytes() == antes


def test_importa_reporte_generado_sin_inferir_clasificacion(tmp_path) -> None:
    repo = RepositorioControlFletes(tmp_path / "control.json")
    raw = excel([
        ["ID expediente", "Factura", "Proveedor", "Moneda", "Facturado"],
        ["FAC-11", "F001-001", "Empresa Sur", "PEN", 150],
    ], "Operaciones")
    prev = preparar_importacion(raw, repo)
    assert len(prev.listas) == 1
    assert prev.listas[0].identificador == "FAC-11"
    assert prev.listas[0].es_flete is None


@pytest.mark.parametrize(
    "headers",
    [
        ["Proveedor", "Fecha", "Moneda"],
        ["Número", "Otros datos", "Monto"],
    ],
)
def test_rechaza_encabezados_incompatibles(tmp_path, headers) -> None:
    repo = RepositorioControlFletes(tmp_path / "control.json")
    with pytest.raises(ValueError, match="columnas"):
        preparar_importacion(excel([headers, ["A", "2026-01-01", "PEN"]]), repo)


def test_archivo_invalido_no_escribe(tmp_path) -> None:
    repo = RepositorioControlFletes(tmp_path / "control.json")
    with pytest.raises(ValueError, match="xlsx"):
        preparar_importacion(b"not an excel file", repo)
    assert not (tmp_path / "control.json").exists()

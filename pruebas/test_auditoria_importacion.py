"""Casos reales de bancarización ambigua detectados antes de importar."""

from io import BytesIO

import pytest
from openpyxl import Workbook

from agente_comprobantes.control_financiero.auditoria_importacion import (
    auditar_importacion,
    normalizar_referencia_para_busqueda,
)
from agente_comprobantes.control_financiero.importacion_masiva import (
    confirmar_importacion,
    preparar_importacion,
)
from agente_comprobantes.control_financiero.repositorio_json import (
    RepositorioControlFletes,
)

ENCABEZADOS = [
    "NRO. BANCARIZACIÓN",
    "Nro de Guia",
    "Proveedor",
    "N° Factura",
    "Moneda",
    "Monto bancarizado",
    "Monto Facturado",
    "Diferencia",
]


def excel(*datos: list[object]) -> bytes:
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Detalle"
    hoja.append(ENCABEZADOS)
    for registro in datos:
        hoja.append(registro)
    salida = BytesIO()
    libro.save(salida)
    return salida.getvalue()


def registro(
    referencia: object,
    factura: str = "E001-522",
    proveedor: str = "Transportes Loop",
    pago: object = 7000,
    facturado: object = 7000,
    diferencia: object = 0,
) -> list[object]:
    return [
        referencia, "EG07-654", proveedor, factura,
        "PEN (S/.)", pago, facturado, diferencia,
    ]


def vista(tmp_path, datos: bytes):
    repo = RepositorioControlFletes(tmp_path / "control_fletes.json")
    return preparar_importacion(datos, repo), repo


def codigos(auditoria) -> set[str]:
    return {item.codigo for item in auditoria.hallazgos}


def test_fila_sencilla_no_tiene_alertas_de_asignacion(tmp_path) -> None:
    previa, repo = vista(tmp_path, excel(registro("6417006")))
    assert not auditar_importacion(previa).bloquea_importacion
    assert confirmar_importacion(previa, repo) == 1


def test_celda_con_dos_bancarizaciones_bloquea_importacion(tmp_path) -> None:
    previa, repo = vista(
        tmp_path, excel(registro("6537194 Y 340464"))
    )
    auditoria = auditar_importacion(previa)
    assert "REFERENCIAS_MULTIPLES" in codigos(auditoria)
    assert auditoria.bloquea_importacion
    with pytest.raises(ValueError, match="agrupación"):
        confirmar_importacion(previa, repo)
    assert not (tmp_path / "control_fletes.json").exists()
    assert previa.listas[0].datos_origen.campos[
        "NRO. BANCARIZACIÓN"
    ] == "6537194 Y 340464"


def test_mismo_documento_en_dos_filas_se_revisa_sin_perder_pagos(tmp_path) -> None:
    previa, repo = vista(tmp_path, excel(
        registro("OP-A", pago=450, facturado=1000, diferencia=550),
        registro("OP-B", pago=550, facturado=1000, diferencia=450),
    ))
    assert previa.duplicadas == 1
    auditoria = auditar_importacion(previa)
    assert "FACTURA_EN_VARIAS_FILAS" in codigos(auditoria)
    assert auditoria.bloquea_importacion
    with pytest.raises(ValueError, match="agrupación"):
        confirmar_importacion(previa, repo)
    assert not (tmp_path / "control_fletes.json").exists()


def test_referencia_igual_en_facturas_distintas_se_revisa(tmp_path) -> None:
    previa, repo = vista(tmp_path, excel(
        registro("74900971.0", factura="F001-1"),
        registro("74900971", factura="F001-2"),
    ))
    assert previa.duplicadas == 0
    auditoria = auditar_importacion(previa)
    assert "REFERENCIA_COMPARTIDA" in codigos(auditoria)
    assert auditoria.bloquea_importacion
    assert normalizar_referencia_para_busqueda("74900971.0") == "74900971"
    assert previa.listas[0].datos_origen.campos[
        "NRO. BANCARIZACIÓN"
    ] == "74900971.0"
    with pytest.raises(ValueError, match="agrupación"):
        confirmar_importacion(previa, repo)


def test_diferencia_inconsistente_se_reporta_pero_no_se_asume_deuda(tmp_path) -> None:
    previa, repo = vista(tmp_path, excel(
        registro("OP-10", pago=7000, facturado=7100, diferencia=0)
    ))
    auditoria = auditar_importacion(previa)
    assert "DIFERENCIA_POR_REVISAR" in codigos(auditoria)
    assert not auditoria.bloquea_importacion
    assert confirmar_importacion(previa, repo) == 1
    assert repo.listar()[0].datos_origen.campos["Diferencia"] == "0"


def test_referencias_numericas_solo_se_normalizan_para_busqueda() -> None:
    assert normalizar_referencia_para_busqueda("6417006.0") == "6417006"
    assert normalizar_referencia_para_busqueda("00123") == "00123"
    assert normalizar_referencia_para_busqueda("AB-12.0") == "AB-12.0"

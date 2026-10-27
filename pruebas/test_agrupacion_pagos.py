"""Vista previa de agrupación: no fusionar ni acreditar pagos sin regla explícita."""

from decimal import Decimal
from io import BytesIO

from openpyxl import Workbook

from agente_comprobantes.control_financiero.agrupacion_pagos import (
    proponer_agrupaciones,
)
from agente_comprobantes.control_financiero.importacion_masiva import (
    preparar_importacion,
)
from agente_comprobantes.control_financiero.repositorio_json import (
    RepositorioControlFletes,
)


def vista(tmp_path, datos: list[list[object]]):
    libro = Workbook()
    hoja = libro.active
    hoja.append([
        "Nro Bancarizacion", "Factura", "Proveedor",
        "Moneda", "Monto Facturado", "Monto bancarizado",
    ])
    for fila in datos:
        hoja.append(fila)
    stream = BytesIO()
    libro.save(stream)
    repo = RepositorioControlFletes(tmp_path / "control_fletes.json")
    return preparar_importacion(stream.getvalue(), repo)


def test_dos_pagos_de_una_factura_se_muestran_por_separado(tmp_path) -> None:
    previa = vista(tmp_path, [
        ["OP-1", "F001-7", "Transportes Sur", "PEN", 1000, 450],
        ["OP-2", "F001-7", "Transportes Sur", "PEN", 1000, 550],
    ])
    grupos = proponer_agrupaciones(previa)
    assert len(grupos) == 1
    grupo = grupos[0]
    assert grupo.condicion == "CANDIDATA A REVISIÓN"
    assert grupo.filas == (2, 3)
    assert grupo.referencias_originales == ("OP-1", "OP-2")
    assert grupo.facturado_referencia == Decimal("1000")
    assert grupo.pagos_declarados == Decimal("1000")
    assert len(previa.listas) == 1
    assert previa.duplicadas == 1
    assert not (tmp_path / "control_fletes.json").exists()


def test_referencia_compuesta_no_se_reparte_automaticamente(tmp_path) -> None:
    previa = vista(tmp_path, [
        ["6537194 Y 340464", "F001-1", "Transportes Sur", "PEN", 1000, 600],
        ["OP-2", "F001-1", "Transportes Sur", "PEN", 1000, 400],
    ])
    grupo = proponer_agrupaciones(previa)[0]
    assert grupo.condicion == "REQUIERE ACLARACIÓN"
    assert "6537194 Y 340464" in grupo.referencias_originales
    assert any("múltiple" in m for m in grupo.observaciones)


def test_cambio_de_monto_y_moneda_requiere_revision(tmp_path) -> None:
    previa = vista(tmp_path, [
        ["OP-1", "F001-1", "Transportes Sur", "PEN", 1000, 400],
        ["OP-2", "F001-1", "Transportes Sur", "USD", 990, 500],
    ])
    grupo = proponer_agrupaciones(previa)[0]
    assert grupo.condicion == "REQUIERE ACLARACIÓN"
    assert grupo.moneda == "VARIAS"
    assert grupo.facturado_referencia is None
    assert len(grupo.observaciones) >= 2


def test_no_proponer_grupos_para_facturas_distintas(tmp_path) -> None:
    previa = vista(tmp_path, [
        ["OP-1", "F001-1", "Transportes Sur", "PEN", 1000, 400],
        ["OP-2", "F001-2", "Transportes Sur", "PEN", 990, 500],
    ])
    assert proponer_agrupaciones(previa) == ()


def test_referencia_repetida_no_se_toma_como_segundo_pago_confiable(tmp_path) -> None:
    previa = vista(tmp_path, [
        ["OP-1", "F001-1", "Transportes Sur", "PEN", 1000, 400],
        ["OP-1", "F001-1", "Transportes Sur", "PEN", 1000, 400],
    ])
    grupo = proponer_agrupaciones(previa)[0]
    assert grupo.condicion == "REQUIERE ACLARACIÓN"
    assert any("repite" in m for m in grupo.observaciones)



def test_efectivo_repetido_no_es_referencia_unica_en_agrupacion(
    tmp_path,
) -> None:
    previa = vista(tmp_path, [
        ["EFECTIVO", "F001-10", "Transportes Sur", "PEN", 1000, 400],
        ["EFECTIVO?", "F001-10", "Transportes Sur", "PEN", 1000, 600],
    ])
    grupo = proponer_agrupaciones(previa)[0]
    assert grupo.condicion == "REQUIERE ACLARACIÓN"
    assert any("EFECTIVO no identifica" in mensaje for mensaje in grupo.observaciones)
    assert grupo.referencias_originales == ("EFECTIVO", "EFECTIVO?")

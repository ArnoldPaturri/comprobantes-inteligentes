"""El libro central impide acreditar por segunda vez un voucher heredado."""

from decimal import Decimal

import pytest

from agente_comprobantes.control_financiero.archivos import almacen_para_excel
from agente_comprobantes.control_financiero.modelos import MovimientoBancario, OperacionFlete
from agente_comprobantes.control_financiero.repositorio_json import RepositorioControlFletes
from agente_comprobantes.control_financiero.repositorio_movimientos import (
    RepositorioMovimientosCentrales,
)
from agente_comprobantes.control_financiero.revision_pagos import guardar_revision_pago
from agente_comprobantes.control_financiero.servicio_movimientos import (
    adjuntar_voucher_central,
    guardar_borrador_central,
)
from agente_comprobantes.dominio.enumeraciones import Moneda


def test_misma_referencia_central_bloquea_acreditacion_heredada(tmp_path):
    control = RepositorioControlFletes(tmp_path / "control_fletes.json")
    central = RepositorioMovimientosCentrales(
        tmp_path / "movimientos_bancarios_centrales.json"
    )
    op = OperacionFlete(
        identificador="FAC-1",
        numero_factura="F001-1",
        moneda=Moneda.PEN,
        monto_facturado=Decimal("1000"),
    )
    control.agregar(op)
    guardar_borrador_central(
        central, control,
        banco="BCP", referencia="OP-100", moneda=Moneda.PEN,
        importe_total="500", aplicaciones=[("FAC-1", "500")],
        sustento="Distribución documentada del pago bancario",
        huella_control=control.huella(), huella_central=central.huella(),
    )
    cambio = op.model_copy(update={
        "movimientos_bancarios": [
            MovimientoBancario(
                importe_aplicado=Decimal("500"),
                moneda=Moneda.PEN,
                referencia="OP-100",
                documento_respaldo="adjunto:" + "a" * 64 + ".pdf",
                verificada=False,
            )
        ],
    })
    control.actualizar(cambio)
    antes = (tmp_path / "control_fletes.json").read_bytes()
    with pytest.raises(ValueError, match="registro central"):
        guardar_revision_pago(
            control, "FAC-1", indice=0, acreditar=True,
            motivo="Se revisó el voucher histórico de forma manual",
            confirmacion=True, version_esperada=0,
        )
    assert (tmp_path / "control_fletes.json").read_bytes() == antes
    assert not control.obtener("FAC-1").movimientos_bancarios[0].verificada


def test_respaldo_duplicado_diferente_referencia_tambien_se_bloquea(tmp_path):
    control = RepositorioControlFletes(tmp_path / "control_fletes.json")
    central = RepositorioMovimientosCentrales(
        tmp_path / "movimientos_bancarios_centrales.json"
    )
    op = OperacionFlete(
        identificador="FAC-1",
        numero_factura="F001-1",
        moneda=Moneda.PEN,
        monto_facturado=Decimal("1000"),
    )
    control.agregar(op)
    movimiento = guardar_borrador_central(
        central, control, banco="BCP", referencia="OP-100",
        moneda=Moneda.PEN, importe_total="500",
        aplicaciones=[("FAC-1", "500")],
        sustento="Transferencia compartida del proveedor",
        huella_control=control.huella(), huella_central=central.huella(),
    )
    voucher = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF"
    vinculado = adjuntar_voucher_central(
        central, control, almacen_para_excel(tmp_path / "registros.xlsx"),
        movimiento.identificador, nombre="voucher.pdf",
        contenido=voucher, motivo="Se adjunta el original escaneado",
        confirmacion=True,
        huella_control=control.huella(), huella_central=central.huella(),
    )
    nuevo = op.model_copy(update={
        "movimientos_bancarios": [
            MovimientoBancario(
                importe_aplicado="500",
                moneda=Moneda.PEN,
                referencia="OP-OTRA",
                documento_respaldo=vinculado.respaldo,
                verificada=False,
            )
        ],
    })
    control.actualizar(nuevo)
    with pytest.raises(ValueError, match="registro central"):
        guardar_revision_pago(
            control, "FAC-1", indice=0, acreditar=True,
            motivo="Cotejo manual del comprobante bancario",
            confirmacion=True, version_esperada=0,
        )

"""Pruebas del resumen de pagos y los saldos por factura."""

from decimal import Decimal

from agente_comprobantes.control_financiero.conciliacion import conciliar_flete
from agente_comprobantes.control_financiero.conciliacion_pagos import (
    construir_resumen_pagos,
)
from agente_comprobantes.control_financiero.modelos import (
    MovimientoBancario,
    OperacionFlete,
)
from agente_comprobantes.dominio.enumeraciones import Moneda


def _pago(
    importe: str,
    *,
    verificada: bool = True,
    referencia: str | None = "OP-001",
    respaldo: str | None = "adjunto:" + "a" * 64 + ".pdf",
) -> MovimientoBancario:
    return MovimientoBancario(
        importe_aplicado=Decimal(importe),
        moneda=Moneda.PEN,
        verificada=verificada,
        referencia=referencia,
        documento_respaldo=respaldo,
    )


def _factura(
    *pagos: MovimientoBancario,
    importe: str = "1000.00",
) -> OperacionFlete:
    return OperacionFlete(
        identificador="EXP-001",
        numero_factura="F001-123",
        proveedor="Proveedor de prueba",
        moneda=Moneda.PEN,
        monto_facturado=Decimal(importe),
        movimientos_bancarios=list(pagos),
    )


def _resumen(operacion: OperacionFlete):
    resultado = conciliar_flete(operacion)
    return construir_resumen_pagos(
        [operacion],
        {operacion.identificador: resultado},
    )[0]


def test_factura_sin_pagos_muestra_saldo_pendiente():
    fila = _resumen(_factura())

    assert fila.estado == "PENDIENTE"
    assert fila.total_acreditado == Decimal("0")
    assert fila.pendiente == Decimal("1000.00")
    assert fila.exceso == Decimal("0")


def test_pago_parcial_calcula_saldo_restante():
    fila = _resumen(_factura(_pago("350.00")))

    assert fila.estado == "PAGO PARCIAL"
    assert fila.total_acreditado == Decimal("350.00")
    assert fila.pendiente == Decimal("650.00")
    assert fila.exceso == Decimal("0")


def test_pago_exactamente_igual_al_neto_marca_factura_pagada():
    fila = _resumen(_factura(_pago("1000.00")))

    assert fila.estado == "PAGADA"
    assert fila.pendiente == Decimal("0")
    assert fila.exceso == Decimal("0")


def test_pago_superior_al_neto_muestra_exceso():
    fila = _resumen(_factura(_pago("1250.00")))

    assert fila.estado == "SOBREPAGADA"
    assert fila.pendiente == Decimal("0")
    assert fila.exceso == Decimal("250.00")


def test_pago_sin_validar_no_reduce_saldo_y_se_muestra_aparte():
    fila = _resumen(_factura(_pago("200.00", verificada=False)))

    assert fila.estado == "PENDIENTE"
    assert fila.total_acreditado == Decimal("0")
    assert fila.pendiente == Decimal("1000.00")
    assert fila.registrado_sin_acreditar == Decimal("200.00")
    assert fila.comprobantes_por_revisar == 1


def test_pago_verificado_sin_referencia_o_respaldo_requiere_revision():
    fila = _resumen(
        _factura(_pago("200.00", referencia=None, respaldo=None))
    )

    assert fila.total_acreditado == Decimal("0")
    assert fila.pendiente == Decimal("1000.00")
    assert fila.comprobantes_por_revisar == 1

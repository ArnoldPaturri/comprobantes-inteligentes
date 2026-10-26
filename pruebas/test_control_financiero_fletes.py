"""Pruebas de conciliación documental y resumen de fletes."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from agente_comprobantes.control_financiero import (
    DepositoDetraccion,
    MovimientoBancario,
    NotaCredito,
    OperacionFlete,
    SituacionControl,
    conciliar_flete,
    resumir_operaciones,
)
from agente_comprobantes.dominio.enumeraciones import Moneda


def bancarizacion(importe: str, *, verificada: bool = True) -> MovimientoBancario:
    return MovimientoBancario(
        moneda=Moneda.PEN,
        importe_aplicado=importe,
        referencia="OP-601",
        documento_respaldo="voucher.pdf",
        verificada=verificada,
    )


def detraccion(importe: str, *, verificada: bool = True) -> DepositoDetraccion:
    return DepositoDetraccion(
        moneda=Moneda.PEN,
        importe=importe,
        referencia="SPOT-93",
        documento_respaldo="deposito.pdf",
        verificada=verificada,
    )


def nota_credito(importe: str, *, verificada: bool = True) -> NotaCredito:
    return NotaCredito(
        moneda=Moneda.PEN,
        numero="FC01-0002",
        referencia="NC-002",
        importe=importe,
        documento_respaldo="nota.pdf",
        verificada=verificada,
    )


def operacion(**cambios: object) -> OperacionFlete:
    datos = {
        "identificador": "FLE-001",
        "numero_factura": "F001-007",
        "proveedor": "Transportes Ejemplo",
        "ruc_proveedor": "20123456789",
        "numero_guia": "EG07-642",
        "moneda": Moneda.PEN,
        "monto_facturado": "1000.00",
        "evidencia_factura": "factura.pdf",
        "detraccion_aplica": False,
        "movimientos_bancarios": [bancarizacion("1000.00")],
        "conciliacion_cerrada": True,
    }
    datos.update(cambios)
    return OperacionFlete(**datos)


def test_banco_mas_detraccion_acreditados_no_generan_falsa_diferencia() -> None:
    resultado = conciliar_flete(
        operacion(
            detraccion_aplica=True,
            movimientos_bancarios=[bancarizacion("960.00")],
            depositos_detraccion=[detraccion("40.00")],
        )
    )
    assert resultado.situacion == SituacionControl.CONFORME
    assert resultado.bancarizado_acreditado == Decimal("960.00")
    assert resultado.detraccion_acreditada == Decimal("40.00")
    assert resultado.saldo_por_acreditar == Decimal("0.00")


def test_nota_credito_validada_reduce_base_conciliada() -> None:
    resultado = conciliar_flete(
        operacion(
            movimientos_bancarios=[bancarizacion("900")],
            notas_credito=[nota_credito("100")],
        )
    )
    assert resultado.situacion == SituacionControl.CONFORME
    assert resultado.facturado_neto == Decimal("900")
    assert resultado.notas_credito_acreditadas == Decimal("100")


def test_detraccion_no_definida_obliga_revision() -> None:
    resultado = conciliar_flete(operacion(detraccion_aplica=None))
    assert resultado.situacion == SituacionControl.PENDIENTE
    assert any("detracción" in texto for texto in resultado.observaciones)


def test_detraccion_sin_constancia_deposito_pendiente() -> None:
    resultado = conciliar_flete(
        operacion(detraccion_aplica=True, movimientos_bancarios=[bancarizacion("960")])
    )
    assert resultado.situacion == SituacionControl.PENDIENTE
    assert resultado.saldo_por_acreditar == Decimal("40")


def test_pago_mayor_que_factura_es_observacion() -> None:
    resultado = conciliar_flete(
        operacion(movimientos_bancarios=[bancarizacion("1001")])
    )
    assert resultado.situacion == SituacionControl.OBSERVADA
    assert resultado.saldo_por_acreditar == Decimal("-1")


def test_sin_guia_no_es_conforme() -> None:
    assert conciliar_flete(operacion(numero_guia=None)).situacion == SituacionControl.PENDIENTE


def test_voucher_no_verificado_no_cuenta_como_pago_acreditado() -> None:
    resultado = conciliar_flete(
        operacion(movimientos_bancarios=[bancarizacion("1000", verificada=False)])
    )
    assert resultado.situacion == SituacionControl.PENDIENTE
    assert resultado.bancarizado_acreditado == Decimal("0")


def test_deposito_incompatible_con_detraccion_no_aplica_es_observacion() -> None:
    resultado = conciliar_flete(
        operacion(depositos_detraccion=[detraccion("40")])
    )
    assert resultado.situacion == SituacionControl.OBSERVADA


def test_divisas_diferentes_no_se_consolidan() -> None:
    op = operacion(
        movimientos_bancarios=[
            MovimientoBancario(
                moneda=Moneda.USD,
                importe_aplicado="1000",
                referencia="USD-01",
                documento_respaldo="usd.pdf",
                verificada=True,
            ),
        ]
    )
    resultado = conciliar_flete(op)
    assert resultado.situacion == SituacionControl.PENDIENTE
    assert resultado.bancarizado_acreditado == Decimal("0")
    assert any("moneda" in texto for texto in resultado.observaciones)


@pytest.mark.parametrize("valor", [1.23, "-2", "Infinity", "NaN"])
def test_importes_invalidos_se_rechazan(valor: object) -> None:
    with pytest.raises(ValidationError):
        operacion(monto_facturado=valor)


def test_resumen_agrupa_presupuesto_por_cotizacion_sin_duplicarlo() -> None:
    primera = operacion(
        identificador="FLE-001",
        numero_factura="F001-001",
        codigo_cotizacion="COT-1",
        monto_cotizado="1000",
        monto_facturado="800",
        conciliacion_cerrada=False,
    )
    segunda = operacion(
        identificador="FLE-002",
        numero_factura="F001-002",
        codigo_cotizacion="COT-1",
        monto_cotizado="1000",
        monto_facturado="400",
        conciliacion_cerrada=False,
    )
    resumen = resumir_operaciones([primera, segunda])[0]
    assert resumen.total_presupuestado == Decimal("1000")
    assert resumen.facturado_con_presupuesto == Decimal("1200")
    assert resumen.desviacion_neta_presupuestada == Decimal("200")
    assert resumen.exceso_acumulado_presupuesto == Decimal("200")


def test_factura_sin_cotizacion_no_produce_sobrecosto_artificial() -> None:
    resumen = resumir_operaciones([operacion(codigo_cotizacion=None)])[0]
    assert resumen.total_presupuestado == 0
    assert resumen.facturado_sin_presupuesto == Decimal("1000")
    assert resumen.exceso_acumulado_presupuesto == 0
    assert resumen.cantidad_sin_presupuesto == 1


def test_resumen_separa_monedas() -> None:
    pen = operacion(
        identificador="FLE-001",
        numero_factura="F001-001",
        codigo_cotizacion="COT-1",
        monto_cotizado="1000",
    )
    usd = operacion(
        identificador="FLE-002",
        numero_factura="F001-002",
        codigo_cotizacion="COT-2",
        moneda=Moneda.USD,
        monto_facturado="200",
        monto_cotizado="300",
        movimientos_bancarios=[],
    )
    resultados = resumir_operaciones([pen, usd])
    assert [item.moneda for item in resultados] == [Moneda.PEN, Moneda.USD]
    assert [item.total_presupuestado for item in resultados] == [1000, 300]


def test_factura_repetida_no_se_suma_dos_veces() -> None:
    with pytest.raises(ValueError, match="repetida"):
        resumir_operaciones([operacion(), operacion(identificador="FLE-OTRA")])


def test_presupuestos_conflictivos_detienen_consolidado() -> None:
    with pytest.raises(ValueError, match="presupuestos distintos"):
        resumir_operaciones(
            [
                operacion(numero_factura="F001-001", codigo_cotizacion="COT-1",
                         monto_cotizado="1000"),
                operacion(numero_factura="F001-002", codigo_cotizacion="COT-1",
                         monto_cotizado="2000"),
            ]
        )

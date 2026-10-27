"""Servicio de aplicaciones bancarias, todavía sin impacto en conciliación."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from agente_comprobantes.control_financiero.auditoria_importacion import (
    _referencias,
)
from agente_comprobantes.control_financiero.modelos import OperacionFlete
from agente_comprobantes.control_financiero.movimientos_centrales import (
    AplicacionBancaria,
    MovimientoBancarioCentral,
)
from agente_comprobantes.control_financiero.repositorio_json import (
    RepositorioControlFletes,
)
from agente_comprobantes.control_financiero.repositorio_movimientos import (
    RepositorioMovimientosCentrales,
)
from agente_comprobantes.dominio.enumeraciones import Moneda


def preparar_borrador_central(
    *,
    banco: str,
    referencia: str,
    moneda: Moneda,
    importe_total: str,
    aplicaciones: list[tuple[str, str]],
    sustento: str,
    facturas: list[OperacionFlete],
    previos: list[MovimientoBancarioCentral],
    fecha_operacion: date | None = None,
) -> MovimientoBancarioCentral:
    """Comprobar saldos declarados y referencias sin tocar registros existentes."""
    borrador = MovimientoBancarioCentral(
        identificador="MB-" + uuid4().hex[:12].upper(),
        banco=banco,
        referencia=referencia,
        moneda=moneda,
        importe_total=importe_total,
        fecha_operacion=fecha_operacion,
        aplicaciones=[
            AplicacionBancaria(expediente=ref, importe=importe)
            for ref, importe in aplicaciones
        ],
        sustento=sustento,
    )
    objetivo = _referencias(borrador.referencia)[0]
    for expediente in facturas:
        for pago in expediente.movimientos_bancarios:
            if objetivo in _referencias(pago.referencia or ""):
                raise ValueError(
                    "La referencia ya está presente en un expediente histórico. "
                    "Primero revisa el registro existente; no crees otro pago."
                )
    for movimiento in previos:
        if objetivo in _referencias(movimiento.referencia):
            raise ValueError(
                "La referencia ya existe en el registro central de borradores."
            )

    por_id = {factura.identificador: factura for factura in facturas}
    for aplicacion in borrador.aplicaciones:
        factura = por_id.get(aplicacion.expediente)
        if factura is None:
            raise ValueError(f"No existe la factura {aplicacion.expediente}.")
        if factura.moneda != borrador.moneda:
            raise ValueError("Las aplicaciones deben usar la misma moneda del voucher.")
        prev_borradores = sum(
            (
                item.importe
                for movimiento in previos
                for item in movimiento.aplicaciones
                if item.expediente == factura.identificador
            ),
            Decimal("0"),
        )
        declarado = sum(
            (pago.importe_aplicado for pago in factura.movimientos_bancarios),
            Decimal("0"),
        )
        disponible = factura.monto_facturado - declarado - prev_borradores
        if aplicacion.importe > disponible:
            raise ValueError(
                "La asignación excede el saldo sin pagos ya declarados para "
                f"la factura {factura.numero_factura}. Revisa sus registros previos."
            )
    return borrador


def guardar_borrador_central(
    banco_repo: RepositorioMovimientosCentrales,
    control_repo: RepositorioControlFletes,
    *,
    banco: str,
    referencia: str,
    moneda: Moneda,
    importe_total: str,
    aplicaciones: list[tuple[str, str]],
    sustento: str,
    huella_control: str,
    huella_central: str,
    fecha_operacion: date | None = None,
) -> MovimientoBancarioCentral:
    """Crear borrador en archivo separado; nunca modifica los saldos oficiales."""
    if control_repo.huella() != huella_control:
        raise ValueError("Los expedientes cambiaron; recarga antes de guardar.")
    if banco_repo.huella() != huella_central:
        raise ValueError("El registro central cambió; recarga antes de guardar.")
    borrador = preparar_borrador_central(
        banco=banco,
        referencia=referencia,
        moneda=moneda,
        importe_total=importe_total,
        aplicaciones=aplicaciones,
        sustento=sustento,
        facturas=control_repo.listar(),
        previos=banco_repo.listar(),
        fecha_operacion=fecha_operacion,
    )
    if control_repo.huella() != huella_control:
        raise ValueError("Los expedientes cambiaron durante la revisión.")
    banco_repo.agregar(borrador, huella_esperada=huella_central)
    return borrador

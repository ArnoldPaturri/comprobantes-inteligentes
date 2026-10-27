"""Resumen de pagos por factura para la conciliación financiera."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from agente_comprobantes.control_financiero.conciliacion import ResultadoControlFlete
from agente_comprobantes.control_financiero.modelos import OperacionFlete
from agente_comprobantes.dominio.enumeraciones import Moneda

CERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class FilaConciliacionPago:
    """Importes comparables para identificar saldos, excesos y evidencias pendientes."""

    identificador: str
    factura: str
    proveedor: str
    moneda: Moneda
    facturado_neto: Decimal
    pago_bancario: Decimal
    detraccion: Decimal
    total_acreditado: Decimal
    pendiente: Decimal
    exceso: Decimal
    registrado_sin_acreditar: Decimal
    comprobantes_por_revisar: int
    estado: str


def construir_resumen_pagos(
    operaciones: list[OperacionFlete],
    resultados: Mapping[str, ResultadoControlFlete],
) -> list[FilaConciliacionPago]:
    """Calcula el estado de pago usando solo evidencias documentalmente acreditadas.

    Los importes registrados sin evidencia completa se muestran por separado,
    pero no reducen el saldo pendiente. Un neto negativo requiere revisar ajustes
    y no se clasifica como sobrepago.
    """
    filas: list[FilaConciliacionPago] = []
    for operacion in operaciones:
        resultado = resultados[operacion.identificador]
        declarado_bancario = sum(
            (
                pago.importe_aplicado
                for pago in operacion.movimientos_bancarios
                if pago.moneda == operacion.moneda
            ),
            CERO,
        )
        registrado_sin_acreditar = max(
            declarado_bancario - resultado.bancarizado_acreditado,
            CERO,
        )
        comprobantes_por_revisar = sum(
            not (
                pago.moneda == operacion.moneda
                and pago.verificada
                and pago.referencia
                and pago.documento_respaldo
            )
            for pago in operacion.movimientos_bancarios
        )

        neto = resultado.facturado_neto
        acreditado = resultado.total_acreditado
        pendiente = max(neto - acreditado, CERO)
        exceso = max(acreditado - neto, CERO) if neto >= CERO else CERO

        if neto < CERO:
            estado = "REVISAR AJUSTES"
        elif exceso > CERO:
            estado = "SOBREPAGADA"
        elif pendiente > CERO and acreditado > CERO:
            estado = "PAGO PARCIAL"
        elif pendiente > CERO:
            estado = "PENDIENTE"
        elif neto == CERO and acreditado == CERO:
            estado = "CUBIERTA POR AJUSTES"
        else:
            estado = "PAGADA"

        filas.append(
            FilaConciliacionPago(
                identificador=operacion.identificador,
                factura=operacion.numero_factura,
                proveedor=operacion.proveedor or "Sin proveedor",
                moneda=operacion.moneda,
                facturado_neto=neto,
                pago_bancario=resultado.bancarizado_acreditado,
                detraccion=resultado.detraccion_acreditada,
                total_acreditado=acreditado,
                pendiente=pendiente,
                exceso=exceso,
                registrado_sin_acreditar=registrado_sin_acreditar,
                comprobantes_por_revisar=comprobantes_por_revisar,
                estado=estado,
            )
        )
    return filas

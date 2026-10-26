"""Conciliación documental de fletes sin atribuir validación bancaria automática."""

from __future__ import annotations

from decimal import Decimal

from pydantic import Field

from agente_comprobantes.control_financiero.modelos import (
    EvidenciaFinanciera,
    OperacionFlete,
    SituacionControl,
)
from agente_comprobantes.dominio.modelo_base import ModeloDominio

CERO = Decimal("0")
CENTIMO = Decimal("0.01")


class ResultadoControlFlete(ModeloDominio):
    identificador: str
    situacion: SituacionControl
    facturado: Decimal
    notas_credito_acreditadas: Decimal
    facturado_neto: Decimal
    bancarizado_acreditado: Decimal
    detraccion_acreditada: Decimal
    total_acreditado: Decimal
    saldo_por_acreditar: Decimal
    observaciones: list[str] = Field(default_factory=list)


def _evidencia_completa(item: EvidenciaFinanciera) -> bool:
    return bool(item.verificada and item.referencia and item.documento_respaldo)


def _sumar_importes(registros: list, nombre_campo: str, operacion: OperacionFlete,
                    alertas: list[str]) -> Decimal:
    total = CERO
    for registro in registros:
        if registro.moneda != operacion.moneda:
            alertas.append(
                f"Documento con moneda {registro.moneda.value} distinta de "
                f"la factura ({operacion.moneda.value})."
            )
            continue
        if not _evidencia_completa(registro):
            alertas.append(
                "Existe un movimiento, depósito o nota de crédito sin "
                "verificación, referencia y documento de respaldo."
            )
            continue
        total += getattr(registro, nombre_campo)
    return total


def conciliar_flete(operacion: OperacionFlete) -> ResultadoControlFlete:
    """Calcula el saldo con evidencias verificadas, nunca con importes supuestos.

    Un estado CONFORME requiere evidencia de factura/guía, clasificación
    de detracción, conciliación declarada cerrada y saldo exacto de cero.
    No valida contra SUNAT ni confirma el movimiento con el banco.
    """
    observaciones: list[str] = []
    problemas: list[str] = []

    if not operacion.evidencia_factura:
        observaciones.append("Falta evidencia de la factura.")
    if not operacion.numero_guia:
        observaciones.append("Falta la guía vinculada al flete.")
    if operacion.detraccion_aplica is None:
        observaciones.append("No se ha determinado si corresponde detracción.")

    notas = _sumar_importes(
        operacion.notas_credito, "importe", operacion, observaciones
    )
    bancarizado = _sumar_importes(
        operacion.movimientos_bancarios, "importe_aplicado", operacion, observaciones
    )
    detraccion = _sumar_importes(
        operacion.depositos_detraccion, "importe", operacion, observaciones
    )

    if operacion.detraccion_aplica is True and not operacion.depositos_detraccion:
        observaciones.append("Falta constancia de depósito de detracción.")
    if operacion.detraccion_aplica is False and operacion.depositos_detraccion:
        problemas.append("Hay depósitos de detracción, pero se marcó no aplica.")
    if not operacion.conciliacion_cerrada:
        observaciones.append("La conciliación aún no se ha cerrado.")

    facturado_neto = operacion.monto_facturado - notas
    total_acreditado = bancarizado + detraccion
    saldo = facturado_neto - total_acreditado

    if facturado_neto < CERO:
        problemas.append("Las notas de crédito superan el importe facturado.")
    if saldo < CERO:
        problemas.append("El total acreditado supera el facturado neto.")
    if saldo > CERO and operacion.conciliacion_cerrada and not observaciones:
        problemas.append("Conciliación cerrada con saldo por acreditar.")

    if problemas:
        situacion = SituacionControl.OBSERVADA
    elif observaciones or saldo != CERO:
        situacion = SituacionControl.PENDIENTE
    else:
        situacion = SituacionControl.CONFORME

    return ResultadoControlFlete(
        identificador=operacion.identificador,
        situacion=situacion,
        facturado=operacion.monto_facturado,
        notas_credito_acreditadas=notas,
        facturado_neto=facturado_neto,
        bancarizado_acreditado=bancarizado,
        detraccion_acreditada=detraccion,
        total_acreditado=total_acreditado,
        saldo_por_acreditar=saldo,
        observaciones=[*observaciones, *problemas],
    )

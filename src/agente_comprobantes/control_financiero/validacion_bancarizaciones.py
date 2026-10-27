"""Reglas conservadoras para acreditar documentalmente un voucher.

No se acepta como bancarización una marca EFECTIVO, una referencia
compuesta ni una misma operación duplicada entre facturas. Un movimiento
compartido requiere un proceso aparte de asignación global.
"""

from __future__ import annotations

from agente_comprobantes.control_financiero.auditoria_importacion import (
    _referencias,
)
from agente_comprobantes.control_financiero.archivos import REFERENCIA
from agente_comprobantes.control_financiero.modelos import OperacionFlete
from agente_comprobantes.control_financiero.tipos_referencia import (
    indicador_efectivo,
)


def validar_cotejo_pago(
    operacion: OperacionFlete,
    indice: int,
    *,
    otros_expedientes: list[OperacionFlete] | None = None,
) -> None:
    """Rechaza evidencias ambiguas antes de declarar revisión aprobada.

    Las referencias repetidas legítimamente entre varias facturas se
    bloquean hasta implementar la distribución verificada del movimiento.
    """
    pago = operacion.movimientos_bancarios[indice]
    referencia = (pago.referencia or "").strip()
    if not referencia:
        raise ValueError("No se puede acreditar un pago sin número de operación.")
    if indicador_efectivo(referencia):
        raise ValueError(
            "EFECTIVO no es una referencia de bancarización: aclara el "
            "medio de pago antes de validar esta evidencia."
        )
    partes = _referencias(referencia)
    if len(partes) != 1:
        raise ValueError(
            "La referencia contiene varios pagos: primero desglosa y "
            "documenta cada operación."
        )
    if not pago.documento_respaldo or not REFERENCIA.fullmatch(
        pago.documento_respaldo
    ):
        raise ValueError(
            "Adjunta el comprobante original mediante la aplicación "
            "antes de validar el pago."
        )
    if pago.moneda != operacion.moneda:
        raise ValueError("La moneda del movimiento no coincide con la factura.")

    ref = partes[0]
    operaciones = otros_expedientes if otros_expedientes is not None else [operacion]
    for existente in operaciones:
        for posicion, otro_pago in enumerate(existente.movimientos_bancarios):
            if (
                existente.identificador == operacion.identificador
                and posicion == indice
            ):
                continue
            if ref in _referencias(otro_pago.referencia or ""):
                raise ValueError(
                    "La referencia bancaria ya figura en otro movimiento "
                    "o expediente. Revisa el voucher y la distribución "
                    "del pago antes de acreditarlo."
                )

"""Revisión humana de un comprobante de pago en el control local.

Un importe acreditado aquí corresponde a evidencia DOCUMENTAL revisada
manualmente: no se consulta la cuenta bancaria ni se verifica SUNAT.
"""

from __future__ import annotations

from datetime import UTC, datetime

from agente_comprobantes.control_financiero.modelos import (
    OperacionFlete,
    RevisionExpediente,
)
from agente_comprobantes.control_financiero.repositorio_json import (
    RepositorioControlFletes,
)
from agente_comprobantes.control_financiero.validacion_bancarizaciones import (
    validar_cotejo_pago,
)


def preparar_revision_pago(
    operacion: OperacionFlete,
    *,
    indice: int,
    acreditar: bool,
    motivo: str,
    confirmacion: bool,
    version_esperada: int,
    otros_expedientes: list[OperacionFlete] | None = None,
) -> OperacionFlete:
    """Cambia la revisión documental de un pago, sin editar sus importes."""
    if len(operacion.revisiones) != version_esperada:
        raise ValueError("El expediente cambió: actualiza la página antes de guardar.")
    if not isinstance(indice, int) or isinstance(indice, bool):
        raise ValueError("El índice del movimiento debe ser un entero.")
    if not 0 <= indice < len(operacion.movimientos_bancarios):
        raise ValueError("El movimiento seleccionado no existe.")
    if not confirmacion:
        raise ValueError("Confirma la revisión del documento, importe y referencia.")
    motivo = motivo.strip()
    if len(motivo) < 10:
        raise ValueError("Describe el sustento de la revisión (mínimo 10 caracteres).")

    pago = operacion.movimientos_bancarios[indice]
    if pago.verificada == acreditar:
        raise ValueError("La acreditación documental seleccionada ya está registrada.")

    if acreditar:
        validar_cotejo_pago(
            operacion, indice, otros_expedientes=otros_expedientes
        )

    nuevos_pagos = [
        item.model_dump(mode="python") for item in operacion.movimientos_bancarios
    ]
    nuevos_pagos[indice]["verificada"] = acreditar
    revision = RevisionExpediente(
        fecha=datetime.now(UTC),
        motivo=motivo,
        cambios={
            f"movimientos_bancarios[{indice}].verificada": (
                f"{pago.verificada} → {acreditar}"
            ),
            "referencia": pago.referencia or "",
            "importe_revisado": str(pago.importe_aplicado),
            "moneda": pago.moneda.value,
            "respaldo": pago.documento_respaldo or "",
        },
    )
    datos = operacion.model_dump(mode="python")
    datos["movimientos_bancarios"] = nuevos_pagos
    datos["conciliacion_cerrada"] = False
    datos["revisiones"] = [*operacion.revisiones, revision]
    return OperacionFlete.model_validate(datos)


def guardar_revision_pago(
    repositorio: RepositorioControlFletes,
    identificador: str,
    *,
    indice: int,
    acreditar: bool,
    motivo: str,
    confirmacion: bool,
    version_esperada: int,
) -> OperacionFlete:
    """Guarda en JSON independiente; el Excel original permanece sin cambios."""
    expedientes = repositorio.listar()
    actual = next(
        (op for op in expedientes if op.identificador == identificador),
        None,
    )
    if actual is None:
        raise ValueError(f"No existe el expediente {identificador}.")
    revisado = preparar_revision_pago(
        actual,
        indice=indice,
        acreditar=acreditar,
        motivo=motivo,
        confirmacion=confirmacion,
        version_esperada=version_esperada,
        otros_expedientes=expedientes,
    )
    repositorio.actualizar(revisado)
    return revisado

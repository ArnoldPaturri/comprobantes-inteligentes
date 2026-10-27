"""Auditoría de expedientes existentes sin modificar los registros financieros."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from agente_comprobantes.control_financiero.auditoria_importacion import (
    _campo,
    _referencias,
)
from agente_comprobantes.control_financiero.modelos import OperacionFlete
from agente_comprobantes.control_financiero.tipos_referencia import (
    efectivo_por_confirmar,
    indicador_efectivo,
)


@dataclass(frozen=True, slots=True)
class IncidenciaExpediente:
    identificador: str
    factura: str
    proveedor: str
    tipo: str
    referencia_original: str
    detalle: str
    accion: str


def auditar_expedientes(
    operaciones: list[OperacionFlete],
) -> tuple[IncidenciaExpediente, ...]:
    """Diagnostica referencias ambiguas ya guardadas, sin tocar acreditaciones."""
    hallazgos: list[IncidenciaExpediente] = []
    referencias: dict[str, set[str]] = defaultdict(set)

    for op in operaciones:
        original = (
            _campo(op.datos_origen.campos, "referencia")
            if op.datos_origen is not None else ""
        )
        actuales = [
            movimiento.referencia or "" for movimiento in op.movimientos_bancarios
        ]
        # El dato fuente permanece inmutable, pero una corrección documentada
        # permite que deje de figurar como incidencia ACTIVA.
        tiene_revision_de_origen = any(
            revision.cambios.get("accion") in {
                "desglose_declarado", "reclasificar_efectivo"
            }
            and revision.cambios.get("referencia_original") == original
            for revision in op.revisiones
        )
        candidatos = ([original] if original and not tiene_revision_de_origen
                      else []) + actuales

        for pendiente in op.declaraciones_por_aclarar:
            hallazgos.append(IncidenciaExpediente(
                op.identificador, op.numero_factura, op.proveedor or "",
                "DECLARACIÓN DE PAGO POR ACLARAR",
                pendiente.referencia_original,
                f"Importe declarado: {pendiente.importe_declarado} "
                f"{pendiente.moneda.value}. No es una bancarización acreditada.",
                "Verificar medio de pago, constancia y clasificación. "
                "No aplicar el importe automáticamente.",
            ))
        for valor in candidatos:
            if not valor.strip() or indicador_efectivo(valor):
                continue
            for parte in _referencias(valor):
                referencias[parte].add(op.identificador)

        if any(indicador_efectivo(valor) for valor in candidatos):
            ref = next(
                valor for valor in candidatos if indicador_efectivo(valor)
            )
            hallazgos.append(IncidenciaExpediente(
                op.identificador, op.numero_factura, op.proveedor or "",
                "EFECTIVO POR CONFIRMAR"
                if efectivo_por_confirmar(ref) else "EFECTIVO SIN OPERACIÓN",
                ref,
                "La etiqueta no acredita una bancarización. "
                "Puede existir un movimiento antiguo creado a partir de ella.",
                "Revisar medio de pago y respaldo original; no marcar como "
                "bancarizado sin comprobante verificable.",
            ))

        multiples = next((
            valor for valor in candidatos
            if not indicador_efectivo(valor) and len(_referencias(valor)) > 1
        ), None)
        if multiples is not None:
            hallazgos.append(IncidenciaExpediente(
                op.identificador, op.numero_factura, op.proveedor or "",
                "REFERENCIAS MÚLTIPLES", multiples,
                "Varias referencias comparten un importe declarado sin "
                "distribución individual documentada.",
                "Obtener los comprobantes individuales y sus importes. "
                "No repartir automáticamente el monto declarado.",
            ))

    por_id = {op.identificador: op for op in operaciones}
    for referencia, ids in referencias.items():
        if len(ids) < 2:
            continue
        for identificador in sorted(ids):
            op = por_id[identificador]
            otros = ", ".join(sorted(ids - {identificador}))
            hallazgos.append(IncidenciaExpediente(
                identificador, op.numero_factura, op.proveedor or "",
                "REFERENCIA COMPARTIDA", referencia,
                f"También figura en los expedientes {otros}. "
                "Puede ser un abono distribuido entre facturas.",
                "Contrastar el importe bancario total con lo aplicado a cada "
                "factura; no acreditar el total en todas.",
            ))
    return tuple(sorted(
        hallazgos,
        key=lambda item: (item.identificador, item.tipo, item.referencia_original),
    ))

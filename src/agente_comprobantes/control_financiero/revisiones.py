"""Revisión manual de clasificación y campos de control documental."""

from __future__ import annotations

from datetime import UTC, datetime

from agente_comprobantes.control_financiero.modelos import (
    OperacionFlete,
    RevisionExpediente,
)
from agente_comprobantes.control_financiero.repositorio_json import RepositorioControlFletes


def preparar_revision(
    operacion: OperacionFlete,
    *,
    es_flete: bool | None,
    numero_guia: str | None,
    detraccion_aplica: bool | None,
    motivo: str,
    confirmacion: bool,
) -> OperacionFlete:
    """Solo modifica clasificación, guía y evaluación manual de detracción.

    Nunca acredita pagos ni confirma bancarización o consultas tributarias.
    """
    if not confirmacion:
        raise ValueError("Confirma que revisaste los documentos antes de guardar.")
    motivo = motivo.strip()
    if len(motivo) < 10:
        raise ValueError("Explica el motivo de revisión (al menos 10 caracteres).")
    if es_flete is not True and detraccion_aplica is not None:
        raise ValueError("Solo se clasifica la detracción de operaciones de flete.")

    guia = numero_guia.strip() if numero_guia else None
    cambios = {}
    nuevos = {
        "es_flete": es_flete,
        "numero_guia": guia,
        "detraccion_aplica": detraccion_aplica,
    }
    for campo, valor in nuevos.items():
        anterior = getattr(operacion, campo)
        if anterior != valor:
            cambios[campo] = f"{anterior!s} → {valor!s}"
    if not cambios:
        raise ValueError("No hay cambios que guardar.")

    revision = RevisionExpediente(
        fecha=datetime.now(UTC),
        motivo=motivo,
        cambios=cambios,
    )
    datos = operacion.model_dump(mode="python")
    datos.update(nuevos)
    datos["conciliacion_cerrada"] = False
    datos["revisiones"] = [*operacion.revisiones, revision]
    return OperacionFlete.model_validate(datos)


def guardar_revision(
    repositorio: RepositorioControlFletes,
    identificador: str,
    *,
    es_flete: bool | None,
    numero_guia: str | None,
    detraccion_aplica: bool | None,
    motivo: str,
    confirmacion: bool,
) -> OperacionFlete:
    original = repositorio.obtener(identificador)
    if original is None:
        raise ValueError(f"No existe el expediente {identificador}.")
    nueva = preparar_revision(
        original,
        es_flete=es_flete,
        numero_guia=numero_guia,
        detraccion_aplica=detraccion_aplica,
        motivo=motivo,
        confirmacion=confirmacion,
    )
    repositorio.actualizar(nueva)
    return nueva

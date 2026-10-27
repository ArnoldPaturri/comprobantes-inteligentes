"""Distingue referencias operativas de etiquetas genéricas de pago.

La clasificación es conservadora: una etiqueta EFECTIVO no demuestra
una transferencia bancaria ni la ausencia de una operación bancaria.
"""

from __future__ import annotations

import re


def indicador_efectivo(referencia: str | None) -> bool:
    """Reconoce etiquetas genéricas, no identificadores bancarios únicos."""
    if not referencia:
        return False
    return bool(re.fullmatch(
        r"\s*(?:PAGO\s+(?:EN\s+)?)?EFECTIVO\s*[?.]?\s*",
        referencia,
        flags=re.IGNORECASE,
    ))


def efectivo_por_confirmar(referencia: str | None) -> bool:
    return indicador_efectivo(referencia) and "?" in (referencia or "")

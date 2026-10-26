from __future__ import annotations

from collections.abc import Sequence

from agente_comprobantes.dominio import DocumentExtraction, DocumentType
from agente_comprobantes.excepciones import ExtractionError
from agente_comprobantes.proveedores.base import VisionProvider
from agente_comprobantes.servicios.imagenes import PreparedDocument


class FallbackVisionProvider(VisionProvider):
    """Prueba proveedores secuencialmente hasta obtener una extracción válida."""

    def __init__(
        self,
        providers: Sequence[tuple[str, VisionProvider]],
    ) -> None:
        if not providers:
            raise ValueError(
                "Debes configurar al menos un proveedor de visión."
            )

        self._providers = tuple(providers)

    def extract(
        self,
        document: PreparedDocument,
        expected_type: DocumentType,
    ) -> DocumentExtraction:
        failures: list[str] = []

        for name, provider in self._providers:
            try:
                return provider.extract(
                    document,
                    expected_type,
                )
            except ExtractionError as exc:
                failures.append(f"{name}: {exc}")

        details = " | ".join(failures)

        raise ExtractionError(
            "Ningún proveedor pudo extraer el documento. "
            f"Detalles: {details}"
        )
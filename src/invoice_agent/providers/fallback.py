from __future__ import annotations

from collections.abc import Sequence

from invoice_agent.domain import DocumentExtraction, DocumentType
from invoice_agent.exceptions import ExtractionError
from invoice_agent.providers.base import VisionProvider
from invoice_agent.services.image_service import PreparedDocument


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
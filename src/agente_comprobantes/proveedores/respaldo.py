from __future__ import annotations

from collections.abc import Sequence

from agente_comprobantes.dominio import ExtraccionDocumento, TipoDocumento
from agente_comprobantes.excepciones import ErrorExtraccion
from agente_comprobantes.proveedores.base import ProveedorVision
from agente_comprobantes.servicios.imagenes import DocumentoPreparado


class ProveedorVisionRespaldo(ProveedorVision):
    """Prueba proveedores secuencialmente hasta obtener una extracción válida."""

    def __init__(
        self,
        providers: Sequence[tuple[str, ProveedorVision]],
    ) -> None:
        if not providers:
            raise ValueError(
                "Debes configurar al menos un proveedor de visión."
            )

        self._providers = tuple(providers)

    def extract(
        self,
        document: DocumentoPreparado,
        expected_type: TipoDocumento,
    ) -> ExtraccionDocumento:
        failures: list[str] = []

        for name, provider in self._providers:
            try:
                return provider.extract(
                    document,
                    expected_type,
                )
            except ErrorExtraccion as exc:
                failures.append(f"{name}: {exc}")

        details = " | ".join(failures)

        raise ErrorExtraccion(
            "Ningún proveedor pudo extraer el documento. "
            f"Detalles: {details}"
        )
from __future__ import annotations

from agente_comprobantes.casos_uso.cotizaciones import OperacionesCotizaciones
from agente_comprobantes.casos_uso.facturas import OperacionesFacturas
from agente_comprobantes.casos_uso.pagos import OperacionesPagos
from agente_comprobantes.casos_uso.vinculacion_pagos import OperacionesVinculacionPagos
from agente_comprobantes.dominio import ExtraccionDocumento, TipoDocumento
from agente_comprobantes.proveedores.base import ProveedorVision
from agente_comprobantes.repositorios.base import RepositorioDocumentos
from agente_comprobantes.servicios.conciliacion_facturas import ServicioConciliacionFacturas
from agente_comprobantes.servicios.conciliacion_pagos import ServicioConciliacionPagos
from agente_comprobantes.servicios.duplicados import ServicioDuplicados
from agente_comprobantes.servicios.imagenes import ServicioImagenes
from agente_comprobantes.servicios.validacion import ServicioValidacion


class AgenteComprobantes(
    OperacionesCotizaciones,
    OperacionesFacturas,
    OperacionesPagos,
    OperacionesVinculacionPagos,
):
    """Fachada que coordina los casos de uso sin duplicar responsabilidades."""

    def __init__(
        self,
        provider: ProveedorVision,
        repository: RepositorioDocumentos,
        image_service: ServicioImagenes,
        validation_service: ServicioValidacion,
        duplicate_service: ServicioDuplicados,
        reconciliation_service: ServicioConciliacionFacturas,
        payment_reconciliation_service: ServicioConciliacionPagos,
    ) -> None:
        self._provider = provider
        self._repository = repository
        self._images = image_service
        self._validator = validation_service
        self._duplicates = duplicate_service
        self._reconciliation = reconciliation_service
        self._payment_reconciliation = payment_reconciliation_service

    def preview_extraction(
        self,
        expected_type: TipoDocumento,
        image_paths: list[str],
    ) -> ExtraccionDocumento:
        """Extrae un documento sin validar, conciliar ni guardar registros."""
        prepared = self._images.prepare(image_paths)
        return self._provider.extract(
            prepared,
            expected_type,
        )

    @staticmethod
    def _unique(values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip() for value in values if value and value.strip()))

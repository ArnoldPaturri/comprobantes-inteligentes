from __future__ import annotations

from agente_comprobantes.casos_uso.cotizaciones import OperacionesCotizaciones
from agente_comprobantes.casos_uso.facturas import OperacionesFacturas
from agente_comprobantes.casos_uso.pagos import OperacionesPagos
from agente_comprobantes.dominio import DocumentExtraction, DocumentType
from agente_comprobantes.proveedores.base import VisionProvider
from agente_comprobantes.repositorios.base import DocumentRepository
from agente_comprobantes.servicios.conciliacion_facturas import ReconciliationService
from agente_comprobantes.servicios.conciliacion_pagos import PaymentReconciliationService
from agente_comprobantes.servicios.duplicados import DuplicateService
from agente_comprobantes.servicios.imagenes import ImageService
from agente_comprobantes.servicios.validacion import ValidationService


class ReceiptAgent(OperacionesCotizaciones, OperacionesFacturas, OperacionesPagos):
    """Fachada que coordina los casos de uso sin duplicar responsabilidades."""

    def __init__(
        self,
        provider: VisionProvider,
        repository: DocumentRepository,
        image_service: ImageService,
        validation_service: ValidationService,
        duplicate_service: DuplicateService,
        reconciliation_service: ReconciliationService,
        payment_reconciliation_service: PaymentReconciliationService,
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
        expected_type: DocumentType,
        image_paths: list[str],
    ) -> DocumentExtraction:
        """Extrae un documento sin validar, conciliar ni guardar registros."""
        prepared = self._images.prepare(image_paths)
        return self._provider.extract(
            prepared,
            expected_type,
        )

    @staticmethod
    def _unique(values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip() for value in values if value and value.strip()))

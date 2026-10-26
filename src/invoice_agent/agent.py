from __future__ import annotations

from invoice_agent.domain import DocumentExtraction, DocumentType
from invoice_agent.providers.base import VisionProvider
from invoice_agent.repositories.base import DocumentRepository
from invoice_agent.services.duplicate_service import DuplicateService
from invoice_agent.services.image_service import ImageService
from invoice_agent.services.payment_reconciliation_service import PaymentReconciliationService
from invoice_agent.services.reconciliation_service import ReconciliationService
from invoice_agent.services.validation_service import ValidationService
from invoice_agent.casos_uso.cotizaciones import OperacionesCotizaciones
from invoice_agent.casos_uso.facturas import OperacionesFacturas
from invoice_agent.casos_uso.pagos import OperacionesPagos


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

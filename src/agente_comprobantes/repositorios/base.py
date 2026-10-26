from abc import ABC, abstractmethod
from decimal import Decimal

from agente_comprobantes.dominio import (
    DocumentReference,
    InvoiceRecord,
    PaymentReconciliationResult,
    PaymentRecord,
    QuotationRecord,
    ReconciliationResult,
)


class DocumentRepository(ABC):
    """Contrato de persistencia independiente de Excel o Google Sheets."""

    @property
    @abstractmethod
    def location(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def initialize(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_quotation(self, quotation_code: str) -> QuotationRecord | None:
        raise NotImplementedError

    @abstractmethod
    def list_quotations(self) -> list[QuotationRecord]:
        raise NotImplementedError
    
    @abstractmethod
    def add_quotation(self, quotation: QuotationRecord) -> None:
        raise NotImplementedError

    @abstractmethod
    def add_invoice(
        self,
        invoice: InvoiceRecord,
        quotation: QuotationRecord,
        reconciliation: ReconciliationResult,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_invoice(self, invoice_id: str) -> InvoiceRecord | None:
        raise NotImplementedError

    @abstractmethod
    def list_invoices(
        self,
        quotation_code: str | None = None,
    ) -> list[InvoiceRecord]:
        raise NotImplementedError

    @abstractmethod
    def get_verified_payment_total(self, invoice_id: str) -> Decimal:
        raise NotImplementedError

    @abstractmethod
    def get_payment(self, payment_id: str) -> PaymentRecord | None:
        raise NotImplementedError

    @abstractmethod
    def list_pending_payments(
        self,
        quotation_code: str,
    ) -> list[PaymentRecord]:
        raise NotImplementedError

    @abstractmethod
    def add_payment(
        self,
        payment: PaymentRecord,
        invoice: InvoiceRecord | None = None,
        reconciliation: PaymentReconciliationResult | None = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def link_payment(
        self,
        payment: PaymentRecord,
        invoice: InvoiceRecord,
        reconciliation: PaymentReconciliationResult,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_document_references(self) -> list[DocumentReference]:
        raise NotImplementedError

    @abstractmethod
    def read_sheet(self, sheet_name: str) -> list[dict[str, object]]:
        raise NotImplementedError

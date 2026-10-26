from abc import ABC, abstractmethod
from decimal import Decimal

from agente_comprobantes.dominio import (
    ReferenciaDocumento,
    RegistroFactura,
    ResultadoConciliacionPago,
    RegistroPago,
    RegistroCotizacion,
    ResultadoConciliacion,
)


class RepositorioDocumentos(ABC):
    """Contrato de persistencia independiente de Excel o Google Sheets."""

    @property
    @abstractmethod
    def location(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def initialize(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_quotation(self, quotation_code: str) -> RegistroCotizacion | None:
        raise NotImplementedError

    @abstractmethod
    def list_quotations(self) -> list[RegistroCotizacion]:
        raise NotImplementedError
    
    @abstractmethod
    def add_quotation(self, quotation: RegistroCotizacion) -> None:
        raise NotImplementedError

    @abstractmethod
    def add_invoice(
        self,
        invoice: RegistroFactura,
        quotation: RegistroCotizacion,
        reconciliation: ResultadoConciliacion,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_invoice(self, invoice_id: str) -> RegistroFactura | None:
        raise NotImplementedError

    @abstractmethod
    def list_invoices(
        self,
        quotation_code: str | None = None,
    ) -> list[RegistroFactura]:
        raise NotImplementedError

    @abstractmethod
    def get_verified_payment_total(self, invoice_id: str) -> Decimal:
        raise NotImplementedError

    @abstractmethod
    def get_payment(self, payment_id: str) -> RegistroPago | None:
        raise NotImplementedError

    @abstractmethod
    def list_pending_payments(
        self,
        quotation_code: str,
    ) -> list[RegistroPago]:
        raise NotImplementedError

    @abstractmethod
    def add_payment(
        self,
        payment: RegistroPago,
        invoice: RegistroFactura | None = None,
        reconciliation: ResultadoConciliacionPago | None = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def link_payment(
        self,
        payment: RegistroPago,
        invoice: RegistroFactura,
        reconciliation: ResultadoConciliacionPago,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_document_references(self) -> list[ReferenciaDocumento]:
        raise NotImplementedError

    @abstractmethod
    def read_sheet(self, sheet_name: str) -> list[dict[str, object]]:
        raise NotImplementedError

from abc import ABC, abstractmethod
from decimal import Decimal

from agente_comprobantes.dominio import (
    ReferenciaDocumento,
    RegistroCotizacion,
    RegistroFactura,
    RegistroPago,
    ResultadoConciliacion,
    ResultadoConciliacionPago,
)


class RepositorioDocumentos(ABC):
    """Contrato de persistencia independiente de Excel o Google Sheets."""

    @property
    @abstractmethod
    def ubicacion(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def inicializar(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def obtener_cotizacion(self, quotation_code: str) -> RegistroCotizacion | None:
        raise NotImplementedError

    @abstractmethod
    def listar_cotizaciones(self) -> list[RegistroCotizacion]:
        raise NotImplementedError
    
    @abstractmethod
    def agregar_cotizacion(self, quotation: RegistroCotizacion) -> None:
        raise NotImplementedError

    @abstractmethod
    def agregar_factura(
        self,
        invoice: RegistroFactura,
        quotation: RegistroCotizacion,
        reconciliation: ResultadoConciliacion,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def obtener_factura(self, invoice_id: str) -> RegistroFactura | None:
        raise NotImplementedError

    @abstractmethod
    def listar_facturas(
        self,
        quotation_code: str | None = None,
    ) -> list[RegistroFactura]:
        raise NotImplementedError

    @abstractmethod
    def obtener_total_pagos_verificados(self, invoice_id: str) -> Decimal:
        raise NotImplementedError

    @abstractmethod
    def obtener_pago(self, payment_id: str) -> RegistroPago | None:
        raise NotImplementedError

    @abstractmethod
    def listar_pagos_pendientes(
        self,
        quotation_code: str,
    ) -> list[RegistroPago]:
        raise NotImplementedError

    @abstractmethod
    def agregar_pago(
        self,
        payment: RegistroPago,
        invoice: RegistroFactura | None = None,
        reconciliation: ResultadoConciliacionPago | None = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def vincular_pago(
        self,
        payment: RegistroPago,
        invoice: RegistroFactura,
        reconciliation: ResultadoConciliacionPago,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def listar_referencias_documentos(self) -> list[ReferenciaDocumento]:
        raise NotImplementedError

    @abstractmethod
    def leer_hoja(self, sheet_name: str) -> list[dict[str, object]]:
        raise NotImplementedError

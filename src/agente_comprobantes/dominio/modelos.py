"""Modelos del dominio reexportados desde módulos especializados."""

from agente_comprobantes.dominio.conciliaciones import (
    PaymentReconciliationResult,
    ReconciliationResult,
)
from agente_comprobantes.dominio.cotizaciones import QuotationRecord
from agente_comprobantes.dominio.extraccion import DocumentExtraction
from agente_comprobantes.dominio.facturas import InvoiceRecord
from agente_comprobantes.dominio.modelo_base import DomainModel
from agente_comprobantes.dominio.pagos import PaymentRecord
from agente_comprobantes.dominio.referencias import DocumentReference, DuplicateMatch
from agente_comprobantes.dominio.resultados import PaymentLinkResult, RegistrationResult
from agente_comprobantes.dominio.validacion import ValidationIssue, ValidationReport

__all__ = [
    "DomainModel",
    "DocumentExtraction",
    "ValidationIssue",
    "ValidationReport",
    "DuplicateMatch",
    "DocumentReference",
    "ReconciliationResult",
    "PaymentReconciliationResult",
    "QuotationRecord",
    "InvoiceRecord",
    "PaymentRecord",
    "RegistrationResult",
    "PaymentLinkResult",
]

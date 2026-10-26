"""Modelos del dominio reexportados desde módulos especializados."""

from invoice_agent.domain.modelo_base import DomainModel
from invoice_agent.domain.extraccion import DocumentExtraction
from invoice_agent.domain.validacion import ValidationIssue, ValidationReport
from invoice_agent.domain.referencias import DuplicateMatch, DocumentReference
from invoice_agent.domain.conciliaciones import ReconciliationResult, PaymentReconciliationResult
from invoice_agent.domain.cotizaciones import QuotationRecord
from invoice_agent.domain.facturas import InvoiceRecord
from invoice_agent.domain.pagos import PaymentRecord
from invoice_agent.domain.resultados import RegistrationResult, PaymentLinkResult

__all__ = ["DomainModel", "DocumentExtraction", "ValidationIssue", "ValidationReport", "DuplicateMatch", "DocumentReference", "ReconciliationResult", "PaymentReconciliationResult", "QuotationRecord", "InvoiceRecord", "PaymentRecord", "RegistrationResult", "PaymentLinkResult"]

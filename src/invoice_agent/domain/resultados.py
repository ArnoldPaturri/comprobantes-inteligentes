from __future__ import annotations

from pydantic import Field
from invoice_agent.domain.enums import DocumentType, PaymentLinkStatus, VerificationStatus
from invoice_agent.domain.modelo_base import DomainModel
from invoice_agent.domain.validacion import ValidationReport
from invoice_agent.domain.referencias import DuplicateMatch
from invoice_agent.domain.conciliaciones import ReconciliationResult
from invoice_agent.domain.conciliaciones import PaymentReconciliationResult


class RegistrationResult(DomainModel):
    document_id: str
    document_type: DocumentType
    verification_status: VerificationStatus
    workbook_path: str
    validation: ValidationReport
    duplicates: list[DuplicateMatch] = Field(default_factory=list)
    reconciliation: ReconciliationResult | None = None
    payment_reconciliation: PaymentReconciliationResult | None = None

class PaymentLinkResult(DomainModel):
    payment_id: str
    invoice_id: str
    quotation_code: str
    reconciliation_status: PaymentLinkStatus
    workbook_path: str
    payment_reconciliation: PaymentReconciliationResult

from __future__ import annotations

from pydantic import Field

from agente_comprobantes.dominio.conciliaciones import (
    PaymentReconciliationResult,
    ReconciliationResult,
)
from agente_comprobantes.dominio.enumeraciones import (
    DocumentType,
    PaymentLinkStatus,
    VerificationStatus,
)
from agente_comprobantes.dominio.modelo_base import DomainModel
from agente_comprobantes.dominio.referencias import DuplicateMatch
from agente_comprobantes.dominio.validacion import ValidationReport


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

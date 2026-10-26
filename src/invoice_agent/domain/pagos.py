from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pydantic import Field, field_validator
from invoice_agent.domain.enums import Currency, DocumentType, PaymentLinkStatus, VerificationStatus
from invoice_agent.domain.modelo_base import DomainModel
from invoice_agent.domain.normalizacion import _parse_decimal, _parse_date


class PaymentRecord(DomainModel):
    payment_id: str
    quotation_code: str
    invoice_id: str | None = None
    payment_type: DocumentType
    payment_entity: str | None = None
    operation_number: str | None = None
    paid_amount: Decimal | None = None
    currency: Currency | None = None
    payment_date: date | None = None
    verification_status: VerificationStatus
    reconciliation_status: PaymentLinkStatus = PaymentLinkStatus.PENDING_INVOICE
    source_hash: str
    source_files: list[str]
    duplicate_of: list[str] = Field(default_factory=list)
    registered_at: datetime = Field(default_factory=datetime.now)
    observations: list[str] = Field(default_factory=list)

    _normalize_amount = field_validator("paid_amount", mode="before")(_parse_decimal)
    _normalize_date = field_validator("payment_date", mode="before")(_parse_date)

    @field_validator("quotation_code")
    @classmethod
    def normalize_quotation_code(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError(
                "El código de cotización del pago no puede estar vacío"
            )
        return normalized

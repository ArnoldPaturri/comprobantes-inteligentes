from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import Field, field_validator

from invoice_agent.domain.enums import Currency, PaymentStatus, VerificationStatus
from invoice_agent.domain.modelo_base import DomainModel
from invoice_agent.domain.normalizacion import _parse_date, _parse_decimal


class InvoiceRecord(DomainModel):
    invoice_id: str
    quotation_code: str
    provider: str | None = None
    provider_tax_id: str | None = None
    invoice_number: str | None = None
    concept: str | None = None
    invoiced_amount: Decimal | None = None
    currency: Currency | None = None
    invoice_date: date | None = None
    verification_status: VerificationStatus
    payment_status: PaymentStatus = PaymentStatus.PENDING
    source_hash: str
    source_files: list[str]
    uncertain_fields: list[str] = Field(default_factory=list)
    duplicate_of: list[str] = Field(default_factory=list)
    registered_at: datetime = Field(default_factory=datetime.now)
    observations: list[str] = Field(default_factory=list)

    _normalize_amount = field_validator("invoiced_amount", mode="before")(_parse_decimal)
    _normalize_date = field_validator("invoice_date", mode="before")(_parse_date)

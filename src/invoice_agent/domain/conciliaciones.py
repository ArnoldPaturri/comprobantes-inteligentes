from __future__ import annotations

from decimal import Decimal
from pydantic import Field, field_validator
from invoice_agent.domain.enums import Diagnosis, PaymentStatus
from invoice_agent.domain.modelo_base import DomainModel
from invoice_agent.domain.normalizacion import _parse_decimal
from invoice_agent.domain.validacion import ValidationIssue


class ReconciliationResult(DomainModel):
    quoted_amount: Decimal | None
    invoiced_amount: Decimal | None
    difference: Decimal | None
    deviation_percent: Decimal | None
    diagnosis: Diagnosis
    provider_similarity: float | None = None
    issues: list[ValidationIssue] = Field(default_factory=list)

class PaymentReconciliationResult(DomainModel):
    invoice_amount: Decimal | None
    previously_paid_amount: Decimal = Decimal("0")
    current_payment_amount: Decimal | None
    applied_amount: Decimal = Decimal("0")
    accumulated_paid_amount: Decimal = Decimal("0")
    remaining_amount: Decimal | None
    resulting_payment_status: PaymentStatus
    applied: bool = True
    issues: list[ValidationIssue] = Field(default_factory=list)

    _normalize_invoice_amount = field_validator("invoice_amount", mode="before")(_parse_decimal)
    _normalize_previous_amount = field_validator(
        "previously_paid_amount", mode="before"
    )(_parse_decimal)
    _normalize_current_amount = field_validator(
        "current_payment_amount", mode="before"
    )(_parse_decimal)
    _normalize_applied_amount = field_validator("applied_amount", mode="before")(_parse_decimal)
    _normalize_accumulated_amount = field_validator(
        "accumulated_paid_amount", mode="before"
    )(_parse_decimal)
    _normalize_remaining_amount = field_validator("remaining_amount", mode="before")(
        _parse_decimal
    )

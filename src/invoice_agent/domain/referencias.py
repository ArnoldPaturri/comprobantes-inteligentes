from __future__ import annotations

from datetime import date
from decimal import Decimal
from pydantic import field_validator
from invoice_agent.domain.enums import Currency, DocumentType
from invoice_agent.domain.modelo_base import DomainModel
from invoice_agent.domain.normalizacion import _parse_decimal, _parse_date


class DuplicateMatch(DomainModel):
    document_id: str
    document_type: DocumentType
    score: float
    reasons: list[str]

class DocumentReference(DomainModel):
    document_id: str
    document_type: DocumentType
    provider: str | None = None
    provider_tax_id: str | None = None
    concept: str | None = None
    document_number: str | None = None
    document_date: date | None = None
    amount: Decimal | None = None
    currency: Currency | None = None
    operation_number: str | None = None
    source_hash: str

    _normalize_amount = field_validator("amount", mode="before")(_parse_decimal)
    _normalize_date = field_validator("document_date", mode="before")(_parse_date)

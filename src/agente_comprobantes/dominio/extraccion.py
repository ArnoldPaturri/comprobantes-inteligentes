from __future__ import annotations

import unicodedata
from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import Field, field_validator, model_validator

from agente_comprobantes.dominio.enumeraciones import Currency, DocumentType
from agente_comprobantes.dominio.modelo_base import DomainModel
from agente_comprobantes.dominio.normalizacion import (
    PROVIDER_LABEL_PATTERN,
    _is_missing,
    _parse_date,
    _parse_decimal,
    _sanitize_text,
)


class DocumentExtraction(DomainModel):
    """Salida normalizada del proveedor de visión.

    Los campos ausentes son válidos: se revisan después mediante reglas según el
    tipo de documento. El modelo nunca debe completar un dato que no sea legible.
    """

    document_type: DocumentType
    provider: str | None = None
    provider_tax_id: str | None = None
    concept: str | None = None
    document_number: str | None = None
    document_date: date | None = None
    total_amount_raw: str | None = None
    total_amount: Decimal | None = None
    currency: Currency | None = None
    operation_number: str | None = None
    payment_entity: str | None = None
    quotation_reference: str | None = None
    confidence: float = 0.0
    uncertain_fields: list[str] = Field(default_factory=list)
    observations: list[str] = Field(default_factory=list)

    _normalize_amount = field_validator("total_amount", mode="before")(_parse_decimal)
    _normalize_date = field_validator("document_date", mode="before")(_parse_date)

    @model_validator(mode="before")
    @classmethod
    def nullify_uncertain_zero_amount(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value

        uncertain_fields = value.get("uncertain_fields") or []

        if isinstance(uncertain_fields, str):
            uncertain_names = {uncertain_fields.strip()}
        else:
            uncertain_names = {
                str(item).strip()
                for item in uncertain_fields
                if item not in (None, "")
            }

        if "total_amount" not in uncertain_names:
            return value

        try:
            parsed_amount = _parse_decimal(
                value.get("total_amount")
            )
        except ValueError:
            return value

        if parsed_amount != Decimal("0"):
            return value

        normalized = dict(value)
        normalized["total_amount"] = None
        return normalized

    @field_validator("document_type", mode="before")
    @classmethod
    def normalize_document_type(cls, value: Any) -> DocumentType:
        if isinstance(value, DocumentType):
            return value
        text = str(value or "").strip().upper().replace(" ", "_").replace("-", "_")
        text = "".join(
            character
            for character in unicodedata.normalize("NFKD", text)
            if not unicodedata.combining(character)
        )
        aliases = {
            "QUOTATION": DocumentType.QUOTATION,
            "PRESUPUESTO": DocumentType.QUOTATION,
            "FACTURA_ELECTRONICA": DocumentType.INVOICE,
            "INVOICE": DocumentType.INVOICE,
            "RECIBO": DocumentType.RECEIPT,
            "TRANSFERENCIA": DocumentType.BANK_TRANSFER,
            "TRANSFERENCIA_BCP": DocumentType.BANK_TRANSFER,
            "COMPROBANTE_DE_PAGO": DocumentType.PAYMENT_RECEIPT,
        }
        if text in aliases:
            return aliases[text]
        try:
            return DocumentType(text)
        except ValueError:
            return DocumentType.UNKNOWN

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: Any) -> Currency | None:
        if _is_missing(value):
            return None
        if isinstance(value, Currency):
            return value

        text = str(value).strip().upper()
        normalized = "".join(
            character
            for character in unicodedata.normalize("NFKD", text)
            if not unicodedata.combining(character)
        )

        if (
            "PEN" in normalized
            or "SOL" in normalized
            or normalized.startswith("S/")
        ):
            return Currency.PEN

        if (
            "USD" in normalized
            or "DOLAR" in normalized
            or "US$" in normalized
        ):
            return Currency.USD

        if (
            "EUR" in normalized
            or "EURO" in normalized
            or "€" in normalized
        ):
            return Currency.EUR

        if normalized in {
            "OTRA",
            "OTHER",
            "DESCONOCIDA",
        }:
            return Currency.OTHER

        return Currency.OTHER

    @field_validator("provider", mode="before")
    @classmethod
    def normalize_provider(cls, value: Any) -> str | None:
        if _is_missing(value):
            return None

        cleaned = _sanitize_text(value)

        if _is_missing(cleaned):
            return None

        normalized = PROVIDER_LABEL_PATTERN.sub(
            "",
            cleaned,
            count=1,
        ).strip()

        return normalized or None

    @field_validator(
        "concept",
        "document_number",
        "total_amount_raw",
        "operation_number",
        "payment_entity",
        "quotation_reference",
        mode="before",
    )
        
    @classmethod
    def normalize_optional_text(
        cls,
        value: Any,
    ) -> str | None:
        if _is_missing(value):
            return None

        cleaned = _sanitize_text(value)
        return cleaned or None

    @field_validator("provider_tax_id", mode="before")
    @classmethod
    def normalize_tax_id(cls, value: Any) -> str | None:
        if _is_missing(value):
            return None
        return "".join(character for character in str(value) if character.isdigit()) or None

    @field_validator("confidence", mode="before")
    @classmethod
    def normalize_confidence(cls, value: Any) -> float:
        if _is_missing(value):
            return 0.0
        text = str(value).strip().replace(",", ".")
        is_percentage = text.endswith("%")
        try:
            number = float(text.removesuffix("%"))
        except ValueError:
            return 0.0
        if is_percentage or 1 < number <= 100:
            number /= 100
        return number

    @field_validator(
        "uncertain_fields",
        "observations",
        mode="before",
    )
    @classmethod
    def none_as_empty_list(
        cls,
        value: Any,
    ) -> list[str]:
        if _is_missing(value):
            return []

        values = [value] if isinstance(value, str) else value
        normalized: list[str] = []

        for item in values:
            if item in (None, ""):
                continue

            cleaned = _sanitize_text(item)

            if cleaned and not _is_missing(cleaned):
                normalized.append(cleaned)

        return normalized

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from invoice_agent.domain.enums import (
    Currency,
    Diagnosis,
    DocumentType,
    PaymentLinkStatus,
    PaymentStatus,
    QuotationStatus,
    Severity,
    VerificationStatus,
)

MISSING_TEXT_VALUES = {"", "NULL", "NONE", "N/A", "NA", "NO APLICA", "NO VISIBLE"}

ILLEGAL_CONTROL_CHARACTER_PATTERN = re.compile(
    r"[\x00-\x08\x0B-\x0C\x0E-\x1F]"
)

def _sanitize_text(value: Any) -> str:
    return ILLEGAL_CONTROL_CHARACTER_PATTERN.sub(
        "",
        str(value),
    ).strip()


PROVIDER_LABEL_PATTERN = re.compile(
    r"^\s*(?:"
    r"GIRADO|"
    r"BENEFICIARIO|"
    r"PROVEEDOR|"
    r"DESTINATARIO|"
    r"EMISOR|"
    r"RAZ[ÓO]N\s+SOCIAL|"
    r"A\s+FAVOR\s+DE"
    r")\s*[:=]\s*",
    re.IGNORECASE,
)


def _is_missing(value: Any) -> bool:
    if value is None or value == {} or value == []:
        return True
    return isinstance(value, str) and value.strip().upper() in MISSING_TEXT_VALUES


def _parse_decimal(value: Any) -> Decimal | None:
    if _is_missing(value):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))

    text = str(value).strip().upper()
    for token in ("S/", "PEN", "US$", "USD", "$", " "):
        text = text.replace(token, "")
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        decimal_part = text.rsplit(",", 1)[-1]
        text = text.replace(",", ".") if len(decimal_part) <= 2 else text.replace(",", "")
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"Monto inválido: {value!r}") from exc


def _parse_date(value: Any) -> date | None:
    if _is_missing(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip().split("T", 1)[0]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Fecha inválida: {value!r}")


class DomainModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, use_enum_values=False)


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


class ValidationIssue(DomainModel):
    code: str
    severity: Severity
    field: str | None = None
    message: str


class ValidationReport(DomainModel):
    issues: list[ValidationIssue] = Field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(issue.severity == Severity.ERROR for issue in self.issues)

    @property
    def requires_review(self) -> bool:
        return bool(self.issues)


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


class QuotationRecord(DomainModel):
    quotation_code: str
    provider: str | None = None
    provider_tax_id: str | None = None
    concept: str | None = None
    quoted_amount: Decimal | None = None
    currency: Currency | None = None
    quotation_date: date | None = None
    status: QuotationStatus = QuotationStatus.WAITING_INVOICE
    verification_status: VerificationStatus
    source_hash: str
    source_files: list[str]
    uncertain_fields: list[str] = Field(default_factory=list)
    registered_at: datetime = Field(default_factory=datetime.now)
    observations: list[str] = Field(default_factory=list)

    _normalize_amount = field_validator("quoted_amount", mode="before")(_parse_decimal)
    _normalize_date = field_validator("quotation_date", mode="before")(_parse_date)

    @field_validator("quotation_code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("El código de cotización no puede estar vacío")
        return normalized


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
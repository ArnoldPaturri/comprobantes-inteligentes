from invoice_agent.config import Settings
from invoice_agent.domain import (
    DocumentExtraction,
    DocumentType,
    Severity,
    ValidationIssue,
    ValidationReport,
)

REQUIRED_FIELDS: dict[DocumentType, tuple[str, ...]] = {
    DocumentType.QUOTATION: ("provider", "concept", "total_amount"),
    DocumentType.INVOICE: ("provider", "document_number", "document_date", "total_amount"),
    DocumentType.RECEIPT: ("provider", "document_number", "document_date", "total_amount"),
    DocumentType.BANK_TRANSFER: ("total_amount", "document_date", "operation_number"),
    DocumentType.YAPE: ("total_amount", "document_date", "operation_number"),
    DocumentType.PLIN: ("total_amount", "document_date", "operation_number"),
    DocumentType.POS_VOUCHER: ("total_amount", "document_date", "operation_number"),
    DocumentType.DEPOSIT: ("total_amount", "document_date", "operation_number"),
    DocumentType.PAYMENT_RECEIPT: ("total_amount", "document_date"),
}

PAYMENT_DOCUMENT_TYPES = frozenset(
    {
        DocumentType.BANK_TRANSFER,
        DocumentType.YAPE,
        DocumentType.PLIN,
        DocumentType.POS_VOUCHER,
        DocumentType.DEPOSIT,
        DocumentType.PAYMENT_RECEIPT,
    }
)


class ValidationService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def validate(
        self,
        extraction: DocumentExtraction,
        expected_type: DocumentType,
    ) -> ValidationReport:
        return self._validate(extraction, expected_type, {expected_type})

    def validate_payment(self, extraction: DocumentExtraction) -> ValidationReport:
        """Acepta las variantes soportadas de un comprobante de pago."""

        return self._validate(
            extraction,
            DocumentType.PAYMENT_RECEIPT,
            PAYMENT_DOCUMENT_TYPES,
        )

    def _validate(
        self,
        extraction: DocumentExtraction,
        expected_type: DocumentType,
        accepted_types: set[DocumentType] | frozenset[DocumentType],
    ) -> ValidationReport:
        issues: list[ValidationIssue] = []

        if extraction.document_type not in accepted_types:
            expected_label = (
                "un comprobante de pago válido"
                if len(accepted_types) > 1
                else expected_type.value
            )
            issues.append(
                ValidationIssue(
                    code="DOCUMENT_TYPE_MISMATCH",
                    severity=Severity.ERROR,
                    field="document_type",
                    message=(
                        f"Se esperaba {expected_label}, pero la imagen parece "
                        f"{extraction.document_type.value}."
                    ),
                )
            )

        required_type = (
            extraction.document_type
            if extraction.document_type in accepted_types
            else expected_type
        )
        for field_name in REQUIRED_FIELDS.get(required_type, ()):
            if getattr(extraction, field_name) in (None, ""):
                issues.append(
                    ValidationIssue(
                        code="MISSING_CRITICAL_FIELD",
                        severity=Severity.ERROR,
                        field=field_name,
                        message=f"No se pudo extraer el campo obligatorio: {field_name}.",
                    )
                )

        if extraction.total_amount is not None and extraction.total_amount < 0:
            issues.append(
                ValidationIssue(
                    code="NEGATIVE_AMOUNT",
                    severity=Severity.ERROR,
                    field="total_amount",
                    message="El monto total no puede ser negativo.",
                )
            )

        if extraction.provider_tax_id and len(extraction.provider_tax_id) != 11:
            issues.append(
                ValidationIssue(
                    code="INVALID_PERUVIAN_RUC",
                    severity=Severity.WARNING,
                    field="provider_tax_id",
                    message="El RUC detectado no contiene 11 dígitos.",
                )
            )

        if not 0 <= extraction.confidence <= 1:
            issues.append(
                ValidationIssue(
                    code="INVALID_CONFIDENCE",
                    severity=Severity.ERROR,
                    field="confidence",
                    message="La confianza debe estar entre 0 y 1.",
                )
            )
        elif extraction.confidence < self._settings.min_extraction_confidence:
            issues.append(
                ValidationIssue(
                    code="LOW_CONFIDENCE",
                    severity=Severity.WARNING,
                    field="confidence",
                    message=f"Confianza de extracción baja ({extraction.confidence:.0%}).",
                )
            )

        for field_name in extraction.uncertain_fields:
            issues.append(
                ValidationIssue(
                    code="UNCERTAIN_FIELD",
                    severity=Severity.WARNING,
                    field=field_name,
                    message=f"El campo {field_name} requiere revisión visual.",
                )
            )

        return ValidationReport(issues=self._deduplicate(issues))

    @staticmethod
    def _deduplicate(issues: list[ValidationIssue]) -> list[ValidationIssue]:
        seen: set[tuple[str, str | None]] = set()
        result: list[ValidationIssue] = []
        for issue in issues:
            key = (issue.code, issue.field)
            if key not in seen:
                seen.add(key)
                result.append(issue)
        return result

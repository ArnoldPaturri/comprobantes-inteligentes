from invoice_agent.domain import (
    Currency,
    DocumentExtraction,
    DocumentType,
    Severity,
)
from invoice_agent.services.validation_service import ValidationService


def test_complete_invoice_is_valid(settings) -> None:
    extraction = DocumentExtraction(
        document_type=DocumentType.INVOICE,
        provider="Proveedor SAC",
        document_number="F001-1",
        document_date="2026-09-12",
        total_amount=100,
        currency=Currency.PEN,
        confidence=0.95,
    )

    report = ValidationService(settings).validate(extraction, DocumentType.INVOICE)

    assert report.issues == []
    assert not report.has_errors


def test_missing_amount_and_wrong_type_are_errors(settings) -> None:
    extraction = DocumentExtraction(
        document_type=DocumentType.BANK_TRANSFER,
        confidence=0.6,
        uncertain_fields=["total_amount"],
    )

    report = ValidationService(settings).validate(extraction, DocumentType.INVOICE)

    assert report.has_errors
    assert any(issue.code == "DOCUMENT_TYPE_MISMATCH" for issue in report.issues)
    assert any(
        issue.field == "total_amount" and issue.severity == Severity.ERROR
        for issue in report.issues
    )


def test_yape_is_accepted_as_payment_document(settings) -> None:
    extraction = DocumentExtraction(
        document_type=DocumentType.YAPE,
        total_amount=145,
        document_date="2026-09-16",
        operation_number="03540652",
        currency=Currency.PEN,
        confidence=0.95,
    )

    report = ValidationService(settings).validate_payment(extraction)

    assert report.issues == []


def test_invoice_is_rejected_as_payment_document(settings) -> None:
    extraction = DocumentExtraction(
        document_type=DocumentType.INVOICE,
        provider="Proveedor SAC",
        document_number="F001-1",
        total_amount=145,
        document_date="2026-09-16",
        currency=Currency.PEN,
        confidence=0.95,
    )

    report = ValidationService(settings).validate_payment(extraction)

    assert any(issue.code == "DOCUMENT_TYPE_MISMATCH" for issue in report.issues)

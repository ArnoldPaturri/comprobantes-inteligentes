from agente_comprobantes.dominio import (
    Moneda,
    ExtraccionDocumento,
    TipoDocumento,
    Severidad,
)
from agente_comprobantes.servicios.validacion import ServicioValidacion


def test_complete_invoice_is_valid(settings) -> None:
    extraction = ExtraccionDocumento(
        document_type=TipoDocumento.INVOICE,
        provider="Proveedor SAC",
        document_number="F001-1",
        document_date="2026-09-12",
        total_amount=100,
        currency=Moneda.PEN,
        confidence=0.95,
    )

    report = ServicioValidacion(settings).validate(extraction, TipoDocumento.INVOICE)

    assert report.issues == []
    assert not report.has_errors


def test_missing_amount_and_wrong_type_are_errors(settings) -> None:
    extraction = ExtraccionDocumento(
        document_type=TipoDocumento.BANK_TRANSFER,
        confidence=0.6,
        uncertain_fields=["total_amount"],
    )

    report = ServicioValidacion(settings).validate(extraction, TipoDocumento.INVOICE)

    assert report.has_errors
    assert any(issue.code == "DOCUMENT_TYPE_MISMATCH" for issue in report.issues)
    assert any(
        issue.field == "total_amount" and issue.severity == Severidad.ERROR
        for issue in report.issues
    )


def test_yape_is_accepted_as_payment_document(settings) -> None:
    extraction = ExtraccionDocumento(
        document_type=TipoDocumento.YAPE,
        total_amount=145,
        document_date="2026-09-16",
        operation_number="03540652",
        currency=Moneda.PEN,
        confidence=0.95,
    )

    report = ServicioValidacion(settings).validate_payment(extraction)

    assert report.issues == []


def test_invoice_is_rejected_as_payment_document(settings) -> None:
    extraction = ExtraccionDocumento(
        document_type=TipoDocumento.INVOICE,
        provider="Proveedor SAC",
        document_number="F001-1",
        total_amount=145,
        document_date="2026-09-16",
        currency=Moneda.PEN,
        confidence=0.95,
    )

    report = ServicioValidacion(settings).validate_payment(extraction)

    assert any(issue.code == "DOCUMENT_TYPE_MISMATCH" for issue in report.issues)

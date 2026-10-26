from decimal import Decimal

from agente_comprobantes.dominio import (
    Currency,
    DocumentExtraction,
    DocumentType,
    InvoiceRecord,
    PaymentStatus,
    Severity,
    VerificationStatus,
)
from agente_comprobantes.servicios.conciliacion_pagos import (
    PaymentReconciliationService,
)


def _invoice(amount: str = "100", currency: Currency = Currency.PEN) -> InvoiceRecord:
    return InvoiceRecord(
        invoice_id="FAC-1",
        quotation_code="COT-1",
        invoiced_amount=amount,
        currency=currency,
        verification_status=VerificationStatus.VERIFIED,
        source_hash="a" * 64,
        source_files=["invoice.png"],
    )


def _payment(amount: str, currency: Currency = Currency.PEN) -> DocumentExtraction:
    return DocumentExtraction(
        document_type=DocumentType.BANK_TRANSFER,
        total_amount=amount,
        currency=currency,
        document_date="2026-09-16",
        operation_number="123456",
        confidence=0.95,
    )


def test_exact_payment_marks_invoice_as_paid() -> None:
    result = PaymentReconciliationService().compare(_invoice(), _payment("100"))

    assert result.accumulated_paid_amount == Decimal("100.00")
    assert result.remaining_amount == Decimal("0.00")
    assert result.resulting_payment_status == PaymentStatus.PAID
    assert result.issues == []


def test_multiple_payments_can_complete_invoice() -> None:
    service = PaymentReconciliationService()
    partial = service.compare(_invoice(), _payment("40"))
    completed = service.compare(
        _invoice(),
        _payment("60"),
        previously_paid=partial.accumulated_paid_amount,
    )

    assert partial.resulting_payment_status == PaymentStatus.PARTIALLY_PAID
    assert completed.resulting_payment_status == PaymentStatus.PAID
    assert completed.accumulated_paid_amount == Decimal("100.00")


def test_overpayment_requires_review() -> None:
    result = PaymentReconciliationService().compare(_invoice(), _payment("101"))

    assert result.resulting_payment_status == PaymentStatus.REVIEW
    assert result.issues[0].code == "PAYMENT_EXCEEDS_INVOICE"
    assert result.issues[0].severity == Severity.WARNING


def test_currency_mismatch_is_an_error() -> None:
    result = PaymentReconciliationService().compare(
        _invoice(currency=Currency.PEN),
        _payment("100", currency=Currency.USD),
    )

    assert any(
        issue.code == "PAYMENT_CURRENCY_MISMATCH" and issue.severity == Severity.ERROR
        for issue in result.issues
    )

def test_suspiciously_low_payment_generates_warning() -> None:
    result = PaymentReconciliationService().compare(
        _invoice(amount="30117.62"),
        _payment("117.62"),
    )

    suspicious_issue = next(
        issue
        for issue in result.issues
        if issue.code == "PAYMENT_AMOUNT_SUSPICIOUSLY_LOW"
    )

    assert suspicious_issue.severity == Severity.WARNING
    assert suspicious_issue.field == "total_amount"
    assert "0.39%" in suspicious_issue.message
    assert "30117.62" in suspicious_issue.message


def test_payment_at_minimum_ratio_is_not_suspicious() -> None:
    service = PaymentReconciliationService(
        min_payment_ratio=Decimal("0.10"),
    )

    result = service.compare(
        _invoice(amount="100"),
        _payment("10"),
    )

    assert not any(
        issue.code == "PAYMENT_AMOUNT_SUSPICIOUSLY_LOW"
        for issue in result.issues
    )
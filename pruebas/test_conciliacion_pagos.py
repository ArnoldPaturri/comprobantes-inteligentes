from decimal import Decimal

from agente_comprobantes.dominio import (
    Moneda,
    ExtraccionDocumento,
    TipoDocumento,
    RegistroFactura,
    EstadoPago,
    Severidad,
    EstadoVerificacion,
)
from agente_comprobantes.servicios.conciliacion_pagos import (
    ServicioConciliacionPagos,
)


def _invoice(amount: str = "100", currency: Moneda = Moneda.PEN) -> RegistroFactura:
    return RegistroFactura(
        invoice_id="FAC-1",
        quotation_code="COT-1",
        invoiced_amount=amount,
        currency=currency,
        verification_status=EstadoVerificacion.VERIFIED,
        source_hash="a" * 64,
        source_files=["invoice.png"],
    )


def _payment(amount: str, currency: Moneda = Moneda.PEN) -> ExtraccionDocumento:
    return ExtraccionDocumento(
        document_type=TipoDocumento.BANK_TRANSFER,
        total_amount=amount,
        currency=currency,
        document_date="2026-09-16",
        operation_number="123456",
        confidence=0.95,
    )


def test_exact_payment_marks_invoice_as_paid() -> None:
    result = ServicioConciliacionPagos().compare(_invoice(), _payment("100"))

    assert result.accumulated_paid_amount == Decimal("100.00")
    assert result.remaining_amount == Decimal("0.00")
    assert result.resulting_payment_status == EstadoPago.PAID
    assert result.issues == []


def test_multiple_payments_can_complete_invoice() -> None:
    service = ServicioConciliacionPagos()
    partial = service.compare(_invoice(), _payment("40"))
    completed = service.compare(
        _invoice(),
        _payment("60"),
        previously_paid=partial.accumulated_paid_amount,
    )

    assert partial.resulting_payment_status == EstadoPago.PARTIALLY_PAID
    assert completed.resulting_payment_status == EstadoPago.PAID
    assert completed.accumulated_paid_amount == Decimal("100.00")


def test_overpayment_requires_review() -> None:
    result = ServicioConciliacionPagos().compare(_invoice(), _payment("101"))

    assert result.resulting_payment_status == EstadoPago.REVIEW
    assert result.issues[0].code == "PAYMENT_EXCEEDS_INVOICE"
    assert result.issues[0].severity == Severidad.WARNING


def test_currency_mismatch_is_an_error() -> None:
    result = ServicioConciliacionPagos().compare(
        _invoice(currency=Moneda.PEN),
        _payment("100", currency=Moneda.USD),
    )

    assert any(
        issue.code == "PAYMENT_CURRENCY_MISMATCH" and issue.severity == Severidad.ERROR
        for issue in result.issues
    )

def test_suspiciously_low_payment_generates_warning() -> None:
    result = ServicioConciliacionPagos().compare(
        _invoice(amount="30117.62"),
        _payment("117.62"),
    )

    suspicious_issue = next(
        issue
        for issue in result.issues
        if issue.code == "PAYMENT_AMOUNT_SUSPICIOUSLY_LOW"
    )

    assert suspicious_issue.severity == Severidad.WARNING
    assert suspicious_issue.field == "total_amount"
    assert "0.39%" in suspicious_issue.message
    assert "30117.62" in suspicious_issue.message


def test_payment_at_minimum_ratio_is_not_suspicious() -> None:
    service = ServicioConciliacionPagos(
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
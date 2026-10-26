from decimal import Decimal

import pytest

from invoice_agent.domain import (
    Currency,
    Diagnosis,
    DocumentExtraction,
    DocumentType,
    PaymentLinkStatus,
    PaymentStatus,
    VerificationStatus,
)
from invoice_agent.exceptions import RecordNotFoundError
from invoice_agent.factory import build_agent
from invoice_agent.repositories.excel_repository import ExcelRepository
from tests.fakes import FakeVisionProvider


def test_end_to_end_with_fake_provider(settings, make_image) -> None:
    quotation_extraction = DocumentExtraction(
        document_type=DocumentType.QUOTATION,
        provider="JJ Consultores e Importadores SAC",
        provider_tax_id="20123456789",
        concept="Materiales de construcción",
        document_number="COT-EXT-9",
        document_date="2026-09-10",
        total_amount="9800.00",
        currency=Currency.PEN,
        confidence=0.96,
    )
    invoice_extraction = DocumentExtraction(
        document_type=DocumentType.INVOICE,
        provider="Jj Consultores E Importadores S.A.C.",
        provider_tax_id="20123456789",
        concept="Materiales de construcción",
        document_number="F001-4952",
        document_date="2026-09-12",
        total_amount="9800.01",
        currency=Currency.PEN,
        confidence=0.95,
    )
    provider = FakeVisionProvider(quotation_extraction, invoice_extraction)
    repository = ExcelRepository(settings.resolved_workbook_path())
    agent = build_agent(settings, provider=provider, repository=repository)
    quotation_image = make_image("quotation.png", color="white", text="Cotización")
    invoice_image = make_image("invoice.png", color="lightblue", text="Factura")

    quotation_result = agent.register_quotation("cot-2026-001", [str(quotation_image)])
    invoice_result = agent.register_invoice("COT-2026-001", [str(invoice_image)])

    assert quotation_result.verification_status == VerificationStatus.VERIFIED
    assert invoice_result.verification_status == VerificationStatus.VERIFIED
    assert invoice_result.reconciliation is not None
    assert invoice_result.reconciliation.difference == Decimal("0.01")
    assert invoice_result.reconciliation.diagnosis == Diagnosis.ABOVE
    assert len(repository.read_sheet("COTIZACIONES")) == 1
    assert len(repository.read_sheet("FACTURAS")) == 1
    assert len(repository.read_sheet("COMPARATIVA")) == 1
    assert [call[1] for call in provider.calls] == [DocumentType.QUOTATION, DocumentType.INVOICE]


def test_missing_quotation_stops_before_calling_ai(settings, make_image) -> None:
    provider = FakeVisionProvider()
    repository = ExcelRepository(settings.resolved_workbook_path())
    agent = build_agent(settings, provider=provider, repository=repository)

    with pytest.raises(RecordNotFoundError, match="No existe la cotización"):
        agent.register_invoice("COT-NO-EXISTE", [str(make_image())])

    assert provider.calls == []


def test_second_invoice_is_saved_as_possible_duplicate(settings, make_image) -> None:
    quotation_extraction = DocumentExtraction(
        document_type=DocumentType.QUOTATION,
        provider="Proveedor SAC",
        concept="Servicio",
        total_amount=100,
        currency=Currency.PEN,
        confidence=0.95,
    )
    invoice_extraction = DocumentExtraction(
        document_type=DocumentType.INVOICE,
        provider="Proveedor SAC",
        provider_tax_id="20123456789",
        concept="Servicio",
        document_number="F001-99",
        document_date="2026-09-12",
        total_amount=100,
        currency=Currency.PEN,
        confidence=0.95,
    )
    provider = FakeVisionProvider(
        quotation_extraction,
        invoice_extraction,
        invoice_extraction.model_copy(deep=True),
    )
    repository = ExcelRepository(settings.resolved_workbook_path())
    agent = build_agent(settings, provider=provider, repository=repository)
    agent.register_quotation("COT-1", [str(make_image("q.png", color="white"))])
    first = agent.register_invoice("COT-1", [str(make_image("f1.png", color="blue"))])
    second = agent.register_invoice("COT-1", [str(make_image("f2.png", color="green"))])

    assert first.verification_status == VerificationStatus.VERIFIED
    assert second.verification_status == VerificationStatus.POSSIBLE_DUPLICATE
    assert second.duplicates[0].document_id == first.document_id
    assert len(repository.read_sheet("FACTURAS")) == 2


def test_payment_updates_invoice_and_duplicate_is_not_applied(settings, make_image) -> None:
    quotation_extraction = DocumentExtraction(
        document_type=DocumentType.QUOTATION,
        provider="Proveedor SAC",
        concept="Servicio",
        total_amount=100,
        currency=Currency.PEN,
        confidence=0.95,
    )
    invoice_extraction = DocumentExtraction(
        document_type=DocumentType.INVOICE,
        provider="Proveedor SAC",
        document_number="F001-100",
        document_date="2026-09-15",
        total_amount=100,
        currency=Currency.PEN,
        confidence=0.95,
    )
    payment_extraction = DocumentExtraction(
        document_type=DocumentType.BANK_TRANSFER,
        provider="Proveedor SAC",
        document_date="2026-09-16",
        total_amount=100,
        currency=Currency.PEN,
        operation_number="99887766",
        payment_entity="BCP",
        confidence=0.95,
    )
    provider = FakeVisionProvider(
        quotation_extraction,
        invoice_extraction,
        payment_extraction,
        payment_extraction.model_copy(deep=True),
    )
    repository = ExcelRepository(settings.resolved_workbook_path())
    agent = build_agent(settings, provider=provider, repository=repository)
    agent.register_quotation("COT-PAGO", [str(make_image("q-pay.png"))])
    invoice = agent.register_invoice("COT-PAGO", [str(make_image("f-pay.png"))])
    payment_image = make_image("payment.png", color="green")

    first_payment = agent.register_payment(
        "COT-PAGO",
        [str(payment_image)],
        invoice_id=invoice.document_id,
    )

    duplicate = agent.register_payment(
        "COT-PAGO",
        [str(payment_image)],
        invoice_id=invoice.document_id,
    )

    assert first_payment.verification_status == VerificationStatus.VERIFIED
    assert first_payment.payment_reconciliation is not None
    assert first_payment.payment_reconciliation.applied is True
    assert first_payment.payment_reconciliation.resulting_payment_status == PaymentStatus.PAID
    assert duplicate.verification_status == VerificationStatus.POSSIBLE_DUPLICATE
    assert duplicate.payment_reconciliation is not None
    assert duplicate.payment_reconciliation.applied is False
    assert duplicate.payment_reconciliation.issues == []
    assert duplicate.payment_reconciliation.accumulated_paid_amount == Decimal("100")
    assert repository.get_invoice(invoice.document_id).payment_status == PaymentStatus.PAID
    assert repository.read_sheet("COMPARATIVA")[0]["Estado de Pago"] == "PAGADO"
    assert len(repository.read_sheet("PAGOS")) == 2

def test_payment_can_be_registered_before_invoice(
    settings,
    make_image,
) -> None:
    quotation_extraction = DocumentExtraction(
        document_type=DocumentType.QUOTATION,
        provider="Proveedor SAC",
        concept="Servicio",
        total_amount=100,
        currency=Currency.PEN,
        confidence=0.95,
    )

    payment_extraction = DocumentExtraction(
        document_type=DocumentType.BANK_TRANSFER,
        provider="Proveedor SAC",
        document_date="2026-09-16",
        total_amount=100,
        currency=Currency.PEN,
        operation_number="11223344",
        payment_entity="Banco Demo",
        confidence=0.95,
    )

    provider = FakeVisionProvider(
        quotation_extraction,
        payment_extraction,
    )
    repository = ExcelRepository(
        settings.resolved_workbook_path()
    )
    agent = build_agent(
        settings,
        provider=provider,
        repository=repository,
    )

    agent.register_quotation(
        "COT-ANTICIPO",
        [str(make_image("q-advance.png"))],
    )

    result = agent.register_payment(
        "COT-ANTICIPO",
        [str(make_image("payment-advance.png"))],
    )

    payment = repository.read_sheet("PAGOS")[0]

    assert result.verification_status == VerificationStatus.VERIFIED
    assert result.payment_reconciliation is None
    assert payment["Cód. Cotización"] == "COT-ANTICIPO"
    assert payment["ID Factura"] is None
    assert (
        payment["Estado Conciliación"]
        == PaymentLinkStatus.PENDING_INVOICE.value
    )


def test_pending_payment_can_be_linked_after_invoice_arrives(
    settings,
    make_image,
) -> None:
    quotation_extraction = DocumentExtraction(
        document_type=DocumentType.QUOTATION,
        provider="Proveedor SAC",
        concept="Servicio",
        total_amount=100,
        currency=Currency.PEN,
        confidence=0.95,
    )

    payment_extraction = DocumentExtraction(
        document_type=DocumentType.BANK_TRANSFER,
        document_date="2026-09-16",
        total_amount=100,
        currency=Currency.PEN,
        operation_number="55667788",
        payment_entity="Banco Demo",
        confidence=0.95,
    )

    invoice_extraction = DocumentExtraction(
        document_type=DocumentType.INVOICE,
        provider="Proveedor SAC",
        document_number="F001-200",
        document_date="2026-09-17",
        total_amount=100,
        currency=Currency.PEN,
        confidence=0.95,
    )

    provider = FakeVisionProvider(
        quotation_extraction,
        payment_extraction,
        invoice_extraction,
    )

    repository = ExcelRepository(
        settings.resolved_workbook_path()
    )
    agent = build_agent(
        settings,
        provider=provider,
        repository=repository,
    )

    agent.register_quotation(
        "COT-LINK",
        [str(make_image("q-link.png"))],
    )

    payment = agent.register_payment(
        "COT-LINK",
        [str(make_image("payment-link.png"))],
    )

    invoice = agent.register_invoice(
        "COT-LINK",
        [str(make_image("invoice-link.png"))],
    )

    calls_before_link = len(provider.calls)

    result = agent.link_payment(
        payment.document_id,
        invoice.document_id,
    )

    stored_payment = repository.get_payment(
        payment.document_id
    )

    assert len(provider.calls) == calls_before_link
    assert (
        result.reconciliation_status
        == PaymentLinkStatus.RECONCILED
    )
    assert result.payment_reconciliation.applied is True
    assert (
        result.payment_reconciliation.remaining_amount
        == Decimal("0.00")
    )
    assert stored_payment is not None
    assert stored_payment.invoice_id == invoice.document_id
    assert (
        stored_payment.reconciliation_status
        == PaymentLinkStatus.RECONCILED
    )
    assert (
        repository.get_invoice(
            invoice.document_id
        ).payment_status
        == PaymentStatus.PAID
    )
    assert (
        repository.read_sheet("COMPARATIVA")[0][
            "Estado de Pago"
        ]
        == "PAGADO"
    )

def test_suspiciously_low_payment_is_not_applied(
    settings,
    make_image,
) -> None:
    quotation_extraction = DocumentExtraction(
        document_type=DocumentType.QUOTATION,
        provider="Proveedor SAC",
        concept="Servicio",
        total_amount="30117.62",
        currency=Currency.PEN,
        confidence=0.95,
    )

    invoice_extraction = DocumentExtraction(
        document_type=DocumentType.INVOICE,
        provider="Proveedor SAC",
        document_number="F001-300",
        document_date="2026-09-15",
        total_amount="30117.62",
        currency=Currency.PEN,
        confidence=0.95,
    )

    payment_extraction = DocumentExtraction(
        document_type=DocumentType.BANK_TRANSFER,
        provider="Proveedor SAC",
        document_date="2026-09-16",
        total_amount_raw="S/ 117.62",
        total_amount="117.62",
        currency=Currency.PEN,
        operation_number="44556677",
        payment_entity="BCP",
        confidence=0.95,
    )

    provider = FakeVisionProvider(
        quotation_extraction,
        invoice_extraction,
        payment_extraction,
    )
    repository = ExcelRepository(
        settings.resolved_workbook_path()
    )
    agent = build_agent(
        settings,
        provider=provider,
        repository=repository,
    )

    agent.register_quotation(
        "COT-SUSPICIOUS",
        [str(make_image("q-suspicious.png"))],
    )

    invoice = agent.register_invoice(
        "COT-SUSPICIOUS",
        [str(make_image("f-suspicious.png"))],
    )

    result = agent.register_payment(
        "COT-SUSPICIOUS",
        [str(make_image("p-suspicious.png"))],
        invoice_id=invoice.document_id,
    )

    stored_invoice = repository.get_invoice(
        invoice.document_id
    )
    stored_payment = repository.get_payment(
        result.document_id
    )

    assert (
        result.verification_status
        == VerificationStatus.REVIEW
    )
    assert result.payment_reconciliation is not None
    assert result.payment_reconciliation.applied is False
    assert (
        result.payment_reconciliation.applied_amount
        == Decimal("0")
    )
    assert (
        result.payment_reconciliation.accumulated_paid_amount
        == Decimal("0")
    )
    assert (
        result.payment_reconciliation.remaining_amount
        == Decimal("30117.62")
    )
    assert any(
        issue.code == "PAYMENT_AMOUNT_SUSPICIOUSLY_LOW"
        for issue in result.payment_reconciliation.issues
    )

    assert stored_invoice is not None
    assert stored_invoice.payment_status == PaymentStatus.PENDING

    assert stored_payment is not None
    assert (
        stored_payment.reconciliation_status
        == PaymentLinkStatus.REVIEW
    )

    comparison = repository.read_sheet("COMPARATIVA")[0]
    assert comparison["Estado de Pago"] == PaymentStatus.PENDING.value

def test_confirmed_extraction_does_not_call_provider_twice(
    settings,
    make_image,
) -> None:
    quotation_extraction = DocumentExtraction(
        document_type=DocumentType.QUOTATION,
        provider="Proveedor Demo SAC",
        concept="Materiales de construcción",
        document_number="COT-DEMO-001",
        document_date="2026-09-16",
        total_amount_raw="S/ 1,000.00",
        total_amount="1000.00",
        currency=Currency.PEN,
        confidence=0.95,
    )

    provider = FakeVisionProvider(quotation_extraction)
    repository = ExcelRepository(
        settings.resolved_workbook_path()
    )
    agent = build_agent(
        settings,
        provider=provider,
        repository=repository,
    )

    image = make_image(
        "quotation-confirmed.png",
        text="Cotización",
    )
    image_paths = [str(image)]

    extraction = agent.preview_extraction(
        DocumentType.QUOTATION,
        image_paths,
    )

    calls_after_preview = len(provider.calls)

    result = agent.register_quotation(
        "COT-CONFIRMED",
        image_paths,
        confirmed_extraction=extraction,
    )

    assert calls_after_preview == 1
    assert len(provider.calls) == 1
    assert result.document_id == "COT-CONFIRMED"
    assert (
        result.verification_status
        == VerificationStatus.VERIFIED
    )
    assert len(repository.read_sheet("COTIZACIONES")) == 1
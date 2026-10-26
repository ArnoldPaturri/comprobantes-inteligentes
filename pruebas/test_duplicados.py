from agente_comprobantes.dominio import (
    Currency,
    DocumentExtraction,
    DocumentReference,
    DocumentType,
)
from agente_comprobantes.servicios.duplicados import DuplicateService


def test_detects_same_invoice_by_tax_id_and_number() -> None:
    extraction = DocumentExtraction(
        document_type=DocumentType.INVOICE,
        provider="Proveedor SAC",
        provider_tax_id="20123456789",
        document_number="F001-0099",
        total_amount=100,
        currency=Currency.PEN,
    )
    existing = [
        DocumentReference(
            document_id="FAC-1",
            document_type=DocumentType.INVOICE,
            provider="Proveedor S.A.C.",
            provider_tax_id="20123456789",
            document_number="F001 0099",
            amount=100,
            currency=Currency.PEN,
            source_hash="a" * 64,
        )
    ]

    matches = DuplicateService().find_matches(extraction, "b" * 64, existing)

    assert matches[0].score == 0.99
    assert matches[0].document_id == "FAC-1"


def test_does_not_compare_invoice_against_quotation() -> None:
    extraction = DocumentExtraction(
        document_type=DocumentType.INVOICE,
        provider="Proveedor SAC",
        total_amount=100,
        currency=Currency.PEN,
    )
    existing = [
        DocumentReference(
            document_id="COT-1",
            document_type=DocumentType.QUOTATION,
            provider="Proveedor SAC",
            amount=100,
            currency=Currency.PEN,
            source_hash="same",
        )
    ]

    assert DuplicateService().find_matches(extraction, "same", existing) == []


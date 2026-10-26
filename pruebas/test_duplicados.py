from agente_comprobantes.dominio import (
    ExtraccionDocumento,
    Moneda,
    ReferenciaDocumento,
    TipoDocumento,
)
from agente_comprobantes.servicios.duplicados import ServicioDuplicados


def test_detects_same_invoice_by_tax_id_and_number() -> None:
    extraction = ExtraccionDocumento(
        document_type=TipoDocumento.INVOICE,
        provider="Proveedor SAC",
        provider_tax_id="20123456789",
        document_number="F001-0099",
        total_amount=100,
        currency=Moneda.PEN,
    )
    existing = [
        ReferenciaDocumento(
            document_id="FAC-1",
            document_type=TipoDocumento.INVOICE,
            provider="Proveedor S.A.C.",
            provider_tax_id="20123456789",
            document_number="F001 0099",
            amount=100,
            currency=Moneda.PEN,
            source_hash="a" * 64,
        )
    ]

    matches = ServicioDuplicados().buscar_coincidencias(extraction, "b" * 64, existing)

    assert matches[0].score == 0.99
    assert matches[0].document_id == "FAC-1"


def test_does_not_compare_invoice_against_quotation() -> None:
    extraction = ExtraccionDocumento(
        document_type=TipoDocumento.INVOICE,
        provider="Proveedor SAC",
        total_amount=100,
        currency=Moneda.PEN,
    )
    existing = [
        ReferenciaDocumento(
            document_id="COT-1",
            document_type=TipoDocumento.QUOTATION,
            provider="Proveedor SAC",
            amount=100,
            currency=Moneda.PEN,
            source_hash="same",
        )
    ]

    assert ServicioDuplicados().buscar_coincidencias(extraction, "same", existing) == []


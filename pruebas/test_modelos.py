from datetime import date
from decimal import Decimal

from agente_comprobantes.dominio import ExtraccionDocumento, Moneda, TipoDocumento


def test_extraction_normalizes_localized_amount_and_date() -> None:
    result = ExtraccionDocumento(
        document_type=TipoDocumento.INVOICE,
        total_amount="S/ 9,800.01",
        document_date="12/09/2026",
        currency=Moneda.PEN,
    )

    assert result.total_amount == Decimal("9800.01")
    assert result.document_date == date(2026, 9, 12)


def test_tax_id_keeps_only_digits() -> None:
    result = ExtraccionDocumento(
        document_type=TipoDocumento.QUOTATION,
        provider_tax_id="RUC 20-60914957-5",
    )

    assert result.provider_tax_id == "20609149575"

def test_normalizes_amount_while_preserving_raw_text() -> None:
    result = ExtraccionDocumento(
        document_type=TipoDocumento.PAYMENT_RECEIPT,
        total_amount_raw="S/ 30 117.62",
        total_amount="30 117.62",
        currency=Moneda.PEN,
        confidence=0.95,
    )

    assert result.total_amount_raw == "S/ 30 117.62"
    assert result.total_amount == Decimal("30117.62")


def test_uncertain_zero_amount_becomes_none() -> None:
    result = ExtraccionDocumento(
        document_type=TipoDocumento.PAYMENT_RECEIPT,
        total_amount_raw=None,
        total_amount=0,
        currency=Moneda.PEN,
        confidence=0.5,
        uncertain_fields=["total_amount"],
    )

    assert result.total_amount is None
    assert "total_amount" in result.uncertain_fields

def test_removes_document_label_from_provider() -> None:
    result = ExtraccionDocumento(
        document_type=TipoDocumento.PAYMENT_RECEIPT,
        provider="GIRADO=MERCANTIL VENTAS SAC",
        total_amount="30117.62",
        currency=Moneda.PEN,
        confidence=0.95,
    )

    assert result.provider == "MERCANTIL VENTAS SAC"

def test_removes_illegal_control_characters_from_text() -> None:
    result = ExtraccionDocumento(
        document_type=TipoDocumento.INVOICE,
        provider="ACME\x1d S.A.C.",
        concept="VENTA\x07 DE CEMENTO",
        observations=["Documento\x00 revisado"],
        confidence=0.95,
    )

    assert result.provider == "ACME S.A.C."
    assert result.concept == "VENTA DE CEMENTO"
    assert result.observations == ["Documento revisado"]
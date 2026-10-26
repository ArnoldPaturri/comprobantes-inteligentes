from decimal import Decimal

from agente_comprobantes.dominio import (
    Diagnostico,
    EstadoVerificacion,
    ExtraccionDocumento,
    Moneda,
    RegistroCotizacion,
    TipoDocumento,
)
from agente_comprobantes.servicios.conciliacion_facturas import ServicioConciliacionFacturas


def quotation(amount: str = "9800.00", provider: str = "JJ Consultores SAC") -> RegistroCotizacion:
    return RegistroCotizacion(
        quotation_code="COT-001",
        provider=provider,
        provider_tax_id="20123456789",
        concept="Materiales",
        quoted_amount=amount,
        currency=Moneda.PEN,
        quotation_date="2026-09-10",
        verification_status=EstadoVerificacion.VERIFIED,
        source_hash="a" * 64,
        source_files=["cotizacion.png"],
    )


def invoice(
    amount: str = "9800.01",
    provider: str = "J.J. Consultores S.A.C.",
) -> ExtraccionDocumento:
    return ExtraccionDocumento(
        document_type=TipoDocumento.INVOICE,
        provider=provider,
        total_amount=amount,
        currency=Moneda.PEN,
        confidence=0.95,
    )


def test_calculates_difference_and_deviation(settings) -> None:
    result = ServicioConciliacionFacturas(settings).comparar(quotation(), invoice())

    assert result.difference == Decimal("0.01")
    assert result.deviation_percent == Decimal("0.0001")
    assert result.diagnosis == Diagnostico.ABOVE
    assert result.issues == []


def test_marks_supplier_mismatch(settings) -> None:
    result = ServicioConciliacionFacturas(settings).comparar(
        quotation(provider="Proveedor Uno SAC"),
        invoice(provider="Empresa Completamente Distinta EIRL"),
    )

    assert any(issue.code == "SUPPLIER_MISMATCH" for issue in result.issues)


def test_zero_quotation_amount_has_no_percentage(settings) -> None:
    result = ServicioConciliacionFacturas(settings).comparar(
        quotation(amount="0"), invoice(amount="5")
    )

    assert result.difference == Decimal("5.00")
    assert result.deviation_percent is None
    assert any(issue.code == "ZERO_QUOTED_AMOUNT" for issue in result.issues)

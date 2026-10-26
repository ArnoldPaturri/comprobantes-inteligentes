from decimal import Decimal

import pytest

from agente_comprobantes.dominio import (
    Diagnostico,
    EstadoPago,
    EstadoVerificacion,
    Moneda,
    RegistroCotizacion,
    RegistroFactura,
    ResultadoConciliacion,
)
from agente_comprobantes.excepciones import ErrorCodigoDuplicado
from agente_comprobantes.repositorios.repositorio_excel import RepositorioExcel


def test_repository_creates_four_sheets_and_roundtrips(settings) -> None:
    repository = RepositorioExcel(settings.resolved_workbook_path())
    quotation = RegistroCotizacion(
        quotation_code="cot-001",
        provider="Proveedor SAC",
        provider_tax_id="20123456789",
        concept="Materiales",
        quoted_amount="100.00",
        currency=Moneda.PEN,
        quotation_date="2026-09-10",
        verification_status=EstadoVerificacion.VERIFIED,
        source_hash="a" * 64,
        source_files=["cot.png"],
    )

    repository.add_quotation(quotation)
    loaded = repository.get_quotation("COT-001")

    assert loaded is not None
    assert loaded.quotation_code == "COT-001"
    assert loaded.quoted_amount == Decimal("100")
    assert repository.read_sheet("FACTURAS") == []
    assert repository.read_sheet("PAGOS") == []

    with pytest.raises(ErrorCodigoDuplicado):
        repository.add_quotation(quotation)


def test_add_invoice_updates_comparison(settings) -> None:
    repository = RepositorioExcel(settings.resolved_workbook_path())
    quotation = RegistroCotizacion(
        quotation_code="COT-002",
        provider="Proveedor SAC",
        concept="Servicio",
        quoted_amount="100",
        currency=Moneda.PEN,
        verification_status=EstadoVerificacion.VERIFIED,
        source_hash="a" * 64,
        source_files=["q.png"],
    )
    repository.add_quotation(quotation)
    invoice = RegistroFactura(
        invoice_id="FAC-1",
        quotation_code="COT-002",
        provider="Proveedor SAC",
        invoice_number="F001-1",
        concept="Servicio",
        invoiced_amount="105",
        currency=Moneda.PEN,
        invoice_date="2026-09-12",
        verification_status=EstadoVerificacion.VERIFIED,
        payment_status=EstadoPago.PENDING,
        source_hash="b" * 64,
        source_files=["f.png"],
    )
    reconciliation = ResultadoConciliacion(
        quoted_amount=Decimal("100"),
        invoiced_amount=Decimal("105"),
        difference=Decimal("5"),
        deviation_percent=Decimal("5"),
        diagnosis=Diagnostico.ABOVE,
    )

    repository.add_invoice(invoice, quotation, reconciliation)

    comparison = repository.read_sheet("COMPARATIVA")
    assert comparison[0]["Cód. Cotización"] == "COT-002"
    assert comparison[0]["Diferencia ($)"] == 5
    assert repository.get_quotation("COT-002").status.value == "FACTURADA"

def test_excel_value_removes_illegal_characters() -> None:
    assert (
        RepositorioExcel._excel_value(
            "ACME\x1d S.A.C."
        )
        == "ACME S.A.C."
    )

    assert (
        RepositorioExcel._excel_value(
            ["UNO\x00", "DOS"]
        )
        == "UNO | DOS"
    )
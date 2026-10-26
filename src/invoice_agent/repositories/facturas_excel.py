from __future__ import annotations

from decimal import Decimal

from openpyxl import load_workbook

from invoice_agent.domain import (
    InvoiceRecord,
    QuotationRecord,
    QuotationStatus,
    ReconciliationResult,
    VerificationStatus,
)
from invoice_agent.repositories.esquemas_excel import COMPARISON_HEADERS, INVOICE_HEADERS


class OperacionesFacturasExcel:
    def add_invoice(
        self,
        invoice: InvoiceRecord,
        quotation: QuotationRecord,
        reconciliation: ReconciliationResult,
    ) -> None:
        self.initialize()
        workbook = load_workbook(self._path)
        self._append_mapping(
            workbook["FACTURAS"],
            INVOICE_HEADERS,
            {
                "ID Factura": invoice.invoice_id,
                "Cód. Cotización": invoice.quotation_code,
                "Proveedor": invoice.provider,
                "RUC Proveedor": invoice.provider_tax_id,
                "N° Factura": invoice.invoice_number,
                "Concepto / Descripción": invoice.concept,
                "Monto Facturado": invoice.invoiced_amount,
                "Moneda": invoice.currency,
                "Fecha Factura": invoice.invoice_date,
                "Estado Verificación": invoice.verification_status,
                "Estado de Pago": invoice.payment_status,
                "Hash Documento": invoice.source_hash,
                "Archivos Origen": invoice.source_files,
                "Campos Inciertos": invoice.uncertain_fields,
                "Posible Duplicado De": invoice.duplicate_of,
                "Fecha Registro": invoice.registered_at,
                "Acción / Observaciones": invoice.observations,
            },
        )
        self._append_mapping(
            workbook["COMPARATIVA"],
            COMPARISON_HEADERS,
            {
                "Cód. Cotización": invoice.quotation_code,
                "Proveedor": invoice.provider or quotation.provider,
                "Concepto / Descripción": invoice.concept or quotation.concept,
                "N° Factura": invoice.invoice_number,
                "Monto Cotizado": reconciliation.quoted_amount,
                "Monto Facturado": reconciliation.invoiced_amount,
                "Diferencia ($)": reconciliation.difference,
                "% Desvío": reconciliation.deviation_percent,
                "Diagnóstico": reconciliation.diagnosis,
                "Estado Verificación": invoice.verification_status,
                "Estado de Pago": invoice.payment_status,
                "Fecha Factura": invoice.invoice_date,
                "Acción / Observaciones": invoice.observations,
            },
        )
        self._update_quotation_status(
            workbook["COTIZACIONES"], invoice.quotation_code, QuotationStatus.INVOICED
        )
        self._save_atomic(workbook)

    def get_invoice(self, invoice_id: str) -> InvoiceRecord | None:
        normalized = invoice_id.strip().upper()
        for row in self.read_sheet("FACTURAS"):
            if str(row["ID Factura"]).strip().upper() == normalized:
                return self._invoice_from_row(row)
        return None

    def list_invoices(
        self,
        quotation_code: str | None = None,
    ) -> list[InvoiceRecord]:
        self.initialize()

        invoices = [
            self._invoice_from_row(row)
            for row in self.read_sheet("FACTURAS")
        ]

        if quotation_code is not None:
            normalized_code = quotation_code.strip().upper()

            invoices = [
                invoice
                for invoice in invoices
                if invoice.quotation_code.strip().upper()
                == normalized_code
            ]

        return sorted(
            invoices,
            key=lambda invoice: invoice.registered_at,
            reverse=True,
        )

    def get_verified_payment_total(self, invoice_id: str) -> Decimal:
        normalized = invoice_id.strip().upper()
        total = Decimal("0")
        for row in self.read_sheet("PAGOS"):
            if str(row["ID Factura"]).strip().upper() != normalized:
                continue
            if str(row["Estado Verificación"]) != VerificationStatus.VERIFIED.value:
                continue
            amount = row["Monto Pagado"]
            if amount not in (None, ""):
                total += Decimal(str(amount))
        return total

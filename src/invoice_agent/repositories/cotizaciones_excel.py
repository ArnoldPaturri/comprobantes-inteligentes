from __future__ import annotations

from openpyxl import load_workbook
from invoice_agent.exceptions import DuplicateCodeError
from invoice_agent.repositories.esquemas_excel import QUOTATION_HEADERS
from invoice_agent.domain import QuotationRecord

class OperacionesCotizacionesExcel:
    def get_quotation(self, quotation_code: str) -> QuotationRecord | None:
        normalized = quotation_code.strip().upper()
        for row in self.read_sheet("COTIZACIONES"):
            if str(row["Cód. Cotización"]).strip().upper() == normalized:
                return self._quotation_from_row(row)
        return None

    def list_quotations(self) -> list[QuotationRecord]:
        self.initialize()

        quotations = [
            self._quotation_from_row(row)
            for row in self.read_sheet("COTIZACIONES")
        ]

        return sorted(
            quotations,
            key=lambda quotation: quotation.registered_at,
            reverse=True,
        )

    def add_quotation(self, quotation: QuotationRecord) -> None:
        self.initialize()
        if self.get_quotation(quotation.quotation_code):
            raise DuplicateCodeError(
                f"Ya existe la cotización {quotation.quotation_code}; no se creó otra fila."
            )

        workbook = load_workbook(self._path)
        sheet = workbook["COTIZACIONES"]
        self._append_mapping(
            sheet,
            QUOTATION_HEADERS,
            {
                "Cód. Cotización": quotation.quotation_code,
                "Proveedor": quotation.provider,
                "RUC Proveedor": quotation.provider_tax_id,
                "Concepto / Descripción": quotation.concept,
                "Monto Cotizado": quotation.quoted_amount,
                "Moneda": quotation.currency,
                "Fecha Cotización": quotation.quotation_date,
                "Estado": quotation.status,
                "Estado Verificación": quotation.verification_status,
                "Hash Documento": quotation.source_hash,
                "Archivos Origen": quotation.source_files,
                "Campos Inciertos": quotation.uncertain_fields,
                "Fecha Registro": quotation.registered_at,
                "Acción / Observaciones": quotation.observations,
                
            },
        )
        self._save_atomic(workbook)

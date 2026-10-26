from __future__ import annotations

from agente_comprobantes.dominio import ReferenciaDocumento, TipoDocumento


class ReferenciasExcel:
    def list_document_references(self) -> list[ReferenciaDocumento]:
        self.initialize()
        references: list[ReferenciaDocumento] = []
        for row in self.read_sheet("COTIZACIONES"):
            references.append(
                ReferenciaDocumento(
                    document_id=str(row["Cód. Cotización"]),
                    document_type=TipoDocumento.QUOTATION,
                    provider=self._optional_str(row["Proveedor"]),
                    provider_tax_id=self._optional_str(row["RUC Proveedor"]),
                    concept=self._optional_str(row["Concepto / Descripción"]),
                    document_date=row["Fecha Cotización"],
                    amount=row["Monto Cotizado"],
                    currency=self._optional_currency(row["Moneda"]),
                    source_hash=str(row["Hash Documento"]),
                )
            )
        for row in self.read_sheet("FACTURAS"):
            references.append(
                ReferenciaDocumento(
                    document_id=str(row["ID Factura"]),
                    document_type=TipoDocumento.INVOICE,
                    provider=self._optional_str(row["Proveedor"]),
                    provider_tax_id=self._optional_str(row["RUC Proveedor"]),
                    concept=self._optional_str(row["Concepto / Descripción"]),
                    document_number=self._optional_str(row["N° Factura"]),
                    document_date=row["Fecha Factura"],
                    amount=row["Monto Facturado"],
                    currency=self._optional_currency(row["Moneda"]),
                    source_hash=str(row["Hash Documento"]),
                )
            )
        for row in self.read_sheet("PAGOS"):
            payment_type = self._optional_document_type(row["Tipo de Pago"])
            if payment_type is None:
                continue
            references.append(
                ReferenciaDocumento(
                    document_id=str(row["ID Pago"]),
                    document_type=payment_type,
                    document_date=row["Fecha Pago"],
                    amount=row["Monto Pagado"],
                    currency=self._optional_currency(row["Moneda"]),
                    operation_number=self._optional_str(row["N° Operación"]),
                    source_hash=str(row["Hash Documento"]),
                )
            )
        return references

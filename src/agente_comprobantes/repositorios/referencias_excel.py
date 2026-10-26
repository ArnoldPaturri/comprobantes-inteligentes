from __future__ import annotations

from agente_comprobantes.dominio import ReferenciaDocumento, TipoDocumento


class ReferenciasExcel:
    def listar_referencias_documentos(self) -> list[ReferenciaDocumento]:
        self.inicializar()
        references: list[ReferenciaDocumento] = []
        for row in self.leer_hoja("COTIZACIONES"):
            references.append(
                ReferenciaDocumento(
                    document_id=str(row["Cód. Cotización"]),
                    document_type=TipoDocumento.QUOTATION,
                    provider=self._texto_opcional(row["Proveedor"]),
                    provider_tax_id=self._texto_opcional(row["RUC Proveedor"]),
                    concept=self._texto_opcional(row["Concepto / Descripción"]),
                    document_date=row["Fecha Cotización"],
                    amount=row["Monto Cotizado"],
                    currency=self._moneda_opcional(row["Moneda"]),
                    source_hash=str(row["Hash Documento"]),
                )
            )
        for row in self.leer_hoja("FACTURAS"):
            references.append(
                ReferenciaDocumento(
                    document_id=str(row["ID Factura"]),
                    document_type=TipoDocumento.INVOICE,
                    provider=self._texto_opcional(row["Proveedor"]),
                    provider_tax_id=self._texto_opcional(row["RUC Proveedor"]),
                    concept=self._texto_opcional(row["Concepto / Descripción"]),
                    document_number=self._texto_opcional(row["N° Factura"]),
                    document_date=row["Fecha Factura"],
                    amount=row["Monto Facturado"],
                    currency=self._moneda_opcional(row["Moneda"]),
                    source_hash=str(row["Hash Documento"]),
                )
            )
        for row in self.leer_hoja("PAGOS"):
            payment_type = self._tipo_documento_opcional(row["Tipo de Pago"])
            if payment_type is None:
                continue
            references.append(
                ReferenciaDocumento(
                    document_id=str(row["ID Pago"]),
                    document_type=payment_type,
                    document_date=row["Fecha Pago"],
                    amount=row["Monto Pagado"],
                    currency=self._moneda_opcional(row["Moneda"]),
                    operation_number=self._texto_opcional(row["N° Operación"]),
                    source_hash=str(row["Hash Documento"]),
                )
            )
        return references

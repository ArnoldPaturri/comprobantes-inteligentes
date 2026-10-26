from __future__ import annotations

from decimal import Decimal

from openpyxl import load_workbook

from agente_comprobantes.dominio import (
    EstadoCotizacion,
    EstadoVerificacion,
    RegistroCotizacion,
    RegistroFactura,
    ResultadoConciliacion,
)
from agente_comprobantes.repositorios.esquemas_excel import COMPARISON_HEADERS, INVOICE_HEADERS


class OperacionesFacturasExcel:
    def agregar_factura(
        self,
        invoice: RegistroFactura,
        quotation: RegistroCotizacion,
        reconciliation: ResultadoConciliacion,
    ) -> None:
        self.inicializar()
        workbook = load_workbook(self._path)
        self._agregar_mapeo(
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
        self._agregar_mapeo(
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
        self._actualizar_estado_cotizacion(
            workbook["COTIZACIONES"], invoice.quotation_code, EstadoCotizacion.INVOICED
        )
        self._guardar_atomico(workbook)

    def obtener_factura(self, invoice_id: str) -> RegistroFactura | None:
        normalized = invoice_id.strip().upper()
        for row in self.leer_hoja("FACTURAS"):
            if str(row["ID Factura"]).strip().upper() == normalized:
                return self._factura_desde_fila(row)
        return None

    def listar_facturas(
        self,
        quotation_code: str | None = None,
    ) -> list[RegistroFactura]:
        self.inicializar()

        invoices = [
            self._factura_desde_fila(row)
            for row in self.leer_hoja("FACTURAS")
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

    def obtener_total_pagos_verificados(self, invoice_id: str) -> Decimal:
        normalized = invoice_id.strip().upper()
        total = Decimal("0")
        for row in self.leer_hoja("PAGOS"):
            if str(row["ID Factura"]).strip().upper() != normalized:
                continue
            if str(row["Estado Verificación"]) != EstadoVerificacion.VERIFIED.value:
                continue
            amount = row["Monto Pagado"]
            if amount not in (None, ""):
                total += Decimal(str(amount))
        return total

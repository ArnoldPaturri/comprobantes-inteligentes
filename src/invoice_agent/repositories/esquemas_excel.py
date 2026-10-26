from __future__ import annotations

import re


ILLEGAL_EXCEL_CHARACTER_PATTERN = re.compile(
    r"[\x00-\x08\x0B-\x0C\x0E-\x1F]"
)

QUOTATION_HEADERS = [
    "Cód. Cotización",
    "Proveedor",
    "RUC Proveedor",
    "Concepto / Descripción",
    "Monto Cotizado",
    "Moneda",
    "Fecha Cotización",
    "Estado",
    "Estado Verificación",
    "Hash Documento",
    "Archivos Origen",
    "Campos Inciertos",
    "Fecha Registro",
    "Acción / Observaciones",
]

INVOICE_HEADERS = [
    "ID Factura",
    "Cód. Cotización",
    "Proveedor",
    "RUC Proveedor",
    "N° Factura",
    "Concepto / Descripción",
    "Monto Facturado",
    "Moneda",
    "Fecha Factura",
    "Estado Verificación",
    "Estado de Pago",
    "Hash Documento",
    "Archivos Origen",
    "Campos Inciertos",
    "Posible Duplicado De",
    "Fecha Registro",
    "Acción / Observaciones",
]

COMPARISON_HEADERS = [
    "Cód. Cotización",
    "Proveedor",
    "Concepto / Descripción",
    "N° Factura",
    "Monto Cotizado",
    "Monto Facturado",
    "Diferencia ($)",
    "% Desvío",
    "Diagnóstico",
    "Estado Verificación",
    "Estado de Pago",
    "Fecha Factura",
    "Acción / Observaciones",
]

PAYMENT_HEADERS = [
    "ID Pago",
    "ID Factura",
    "Tipo de Pago",
    "Entidad",
    "N° Operación",
    "Monto Pagado",
    "Moneda",
    "Fecha Pago",
    "Estado Verificación",
    "Hash Documento",
    "Fecha Registro",
    "Acción / Observaciones",
    "Cód. Cotización",
    "Estado Conciliación",
    "Archivos Origen",
    "Posible Duplicado De",
]

SHEETS = {
    "COTIZACIONES": QUOTATION_HEADERS,
    "FACTURAS": INVOICE_HEADERS,
    "COMPARATIVA": COMPARISON_HEADERS,
    "PAGOS": PAYMENT_HEADERS,
}

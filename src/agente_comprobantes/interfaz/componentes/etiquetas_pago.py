from __future__ import annotations

from agente_comprobantes.dominio import RegistroCotizacion, RegistroFactura


def etiqueta_cotizacion(
    quotation: RegistroCotizacion,
) -> str:
    provider = quotation.provider or "Proveedor no identificado"
    amount = (
        f"{quotation.currency.value} {quotation.quoted_amount:,.2f}"
        if quotation.currency is not None
        and quotation.quoted_amount is not None
        else "Monto no disponible"
    )

    return (
        f"{quotation.quotation_code} | "
        f"{provider} | "
        f"{amount}"
    )


def etiqueta_factura(
    invoice: RegistroFactura,
) -> str:
    number = invoice.invoice_number or "Sin número"
    amount = (
        f"{invoice.currency.value} {invoice.invoiced_amount:,.2f}"
        if invoice.currency is not None
        and invoice.invoiced_amount is not None
        else "Monto no disponible"
    )

    return (
        f"{invoice.invoice_id} | "
        f"{number} | "
        f"{amount} | "
        f"{invoice.payment_status.value}"
    )

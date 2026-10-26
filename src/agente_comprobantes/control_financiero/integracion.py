"""Construye borradores de fletes desde el repositorio documental existente.

Las verificaciones OCR no acreditan un movimiento bancario: los pagos
importados permanecen sin verificar hasta su revisión documental.
"""

from __future__ import annotations

from pydantic import Field

from agente_comprobantes.control_financiero.modelos import (
    MovimientoBancario,
    OperacionFlete,
)
from agente_comprobantes.dominio import (
    Moneda,
    RegistroCotizacion,
    RegistroFactura,
    RegistroPago,
)
from agente_comprobantes.dominio.modelo_base import ModeloDominio
from agente_comprobantes.repositorios.base import RepositorioDocumentos


class BorradorFlete(ModeloDominio):
    operacion: OperacionFlete
    advertencias: list[str] = Field(default_factory=list)


def crear_borrador_desde_documentos(
    factura: RegistroFactura,
    cotizacion: RegistroCotizacion | None = None,
    pagos: list[RegistroPago] | None = None,
) -> BorradorFlete:
    """Crea un borrador sin atribuir verificación bancaria, SUNAT ni guías.

    Se conservan las relaciones existentes con los IDs del agente.
    Los montos de pago se incorporan solo como evidencia sin acreditar.
    """
    if factura.invoiced_amount is None or factura.invoiced_amount <= 0:
        raise ValueError("La factura necesita un importe positivo para crear el borrador.")
    if factura.currency is None or factura.currency == Moneda.OTHER:
        raise ValueError("La factura necesita una moneda identificada.")
    if not factura.invoice_number:
        raise ValueError("La factura necesita un número legible y confirmado.")

    if cotizacion is not None and (
        cotizacion.quotation_code.strip().upper()
        != factura.quotation_code.strip().upper()
    ):
        raise ValueError("La cotización no corresponde a la factura seleccionada.")

    advertencias = []
    if cotizacion is None:
        advertencias.append("No se encontró la cotización asociada.")

    movimientos: list[MovimientoBancario] = []
    for pago in pagos or []:
        if pago.invoice_id != factura.invoice_id:
            raise ValueError(f"El pago {pago.payment_id} no corresponde a esta factura.")
        if pago.paid_amount is None or pago.paid_amount <= 0:
            advertencias.append(f"Pago {pago.payment_id} sin importe utilizable.")
            continue
        if pago.currency is None or pago.currency == Moneda.OTHER:
            advertencias.append(f"Pago {pago.payment_id} sin moneda identificada.")
            continue
        if pago.currency != factura.currency:
            advertencias.append(f"Pago {pago.payment_id} con moneda distinta.")
        if not pago.operation_number:
            advertencias.append(f"Pago {pago.payment_id} sin número de operación.")
        movimientos.append(
            MovimientoBancario(
                moneda=pago.currency,
                importe_aplicado=pago.paid_amount,
                referencia=pago.operation_number,
                documento_respaldo=pago.source_files[0] if pago.source_files else None,
                fecha=pago.payment_date,
                verificada=False,
            )
        )

    operacion = OperacionFlete(
        identificador=factura.invoice_id,
        numero_factura=factura.invoice_number,
        moneda=factura.currency,
        monto_facturado=factura.invoiced_amount,
        codigo_cotizacion=factura.quotation_code,
        monto_cotizado=cotizacion.quoted_amount if cotizacion else None,
        proveedor=factura.provider or (cotizacion.provider if cotizacion else None),
        ruc_proveedor=factura.provider_tax_id
        or (cotizacion.provider_tax_id if cotizacion else None),
        fecha_factura=factura.invoice_date,
        evidencia_factura=factura.source_files[0] if factura.source_files else None,
        movimientos_bancarios=movimientos,
    )
    advertencias.append(
        "Los pagos importados no acreditan bancarización: "
        "se requiere revisión de cada comprobante."
    )
    return BorradorFlete(operacion=operacion, advertencias=advertencias)


def crear_borrador_desde_repositorio(
    repositorio: RepositorioDocumentos,
    identificador_factura: str,
) -> BorradorFlete:
    """Lee el Excel heredado sin modificar las cuatro hojas existentes."""
    factura = repositorio.obtener_factura(identificador_factura)
    if factura is None:
        raise ValueError(f"No existe la factura interna {identificador_factura}.")

    cotizacion = repositorio.obtener_cotizacion(factura.quotation_code)
    pagos: list[RegistroPago] = []
    vistos: set[str] = set()
    for fila in repositorio.leer_hoja("PAGOS"):
        if str(fila.get("ID Factura") or "").strip().upper() != factura.invoice_id.upper():
            continue
        codigo = str(fila.get("ID Pago") or "").strip().upper()
        if not codigo or codigo in vistos:
            raise ValueError("Hay pagos duplicados o sin identificador en la hoja PAGOS.")
        vistos.add(codigo)
        pago = repositorio.obtener_pago(codigo)
        if pago is None:
            raise ValueError(f"No se pudo reconstruir el pago {codigo}.")
        pagos.append(pago)

    return crear_borrador_desde_documentos(factura, cotizacion, pagos)

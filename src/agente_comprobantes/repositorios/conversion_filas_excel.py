from __future__ import annotations

from datetime import datetime

from agente_comprobantes.dominio import (
    EstadoCotizacion,
    EstadoPago,
    EstadoVerificacion,
    EstadoVinculacionPago,
    Moneda,
    RegistroCotizacion,
    RegistroFactura,
    RegistroPago,
    TipoDocumento,
)


class ConversionFilasExcel:
    """Reconstruye entidades de dominio desde filas del archivo Excel."""

    @staticmethod
    def _quotation_from_row(row: dict[str, object]) -> RegistroCotizacion:
        return RegistroCotizacion(
            quotation_code=str(row["Cód. Cotización"]),
            provider=ConversionFilasExcel._optional_str(row["Proveedor"]),
            provider_tax_id=ConversionFilasExcel._optional_str(row["RUC Proveedor"]),
            concept=ConversionFilasExcel._optional_str(row["Concepto / Descripción"]),
            quoted_amount=row["Monto Cotizado"],
            currency=ConversionFilasExcel._optional_currency(row["Moneda"]),
            quotation_date=row["Fecha Cotización"],
            status=EstadoCotizacion(str(row["Estado"])),
            verification_status=EstadoVerificacion(str(row["Estado Verificación"])),
            source_hash=str(row["Hash Documento"]),
            source_files=ConversionFilasExcel._split(row["Archivos Origen"]),
            uncertain_fields=ConversionFilasExcel._split(row["Campos Inciertos"]),
            registered_at=row["Fecha Registro"] or datetime.now(),
            observations=ConversionFilasExcel._split(row["Acción / Observaciones"]),
        )

    @staticmethod
    def _invoice_from_row(row: dict[str, object]) -> RegistroFactura:
        return RegistroFactura(
            invoice_id=str(row["ID Factura"]),
            quotation_code=str(row["Cód. Cotización"]),
            provider=ConversionFilasExcel._optional_str(row["Proveedor"]),
            provider_tax_id=ConversionFilasExcel._optional_str(row["RUC Proveedor"]),
            invoice_number=ConversionFilasExcel._optional_str(row["N° Factura"]),
            concept=ConversionFilasExcel._optional_str(row["Concepto / Descripción"]),
            invoiced_amount=row["Monto Facturado"],
            currency=ConversionFilasExcel._optional_currency(row["Moneda"]),
            invoice_date=row["Fecha Factura"],
            verification_status=EstadoVerificacion(str(row["Estado Verificación"])),
            payment_status=EstadoPago(str(row["Estado de Pago"])),
            source_hash=str(row["Hash Documento"]),
            source_files=ConversionFilasExcel._split(row["Archivos Origen"]),
            uncertain_fields=ConversionFilasExcel._split(row["Campos Inciertos"]),
            duplicate_of=ConversionFilasExcel._split(row["Posible Duplicado De"]),
            registered_at=row["Fecha Registro"] or datetime.now(),
            observations=ConversionFilasExcel._split(row["Acción / Observaciones"]),
        )

    @staticmethod
    def _payment_from_row(
        row: dict[str, object],
    ) -> RegistroPago:
        return RegistroPago(
            payment_id=str(row["ID Pago"]),
            quotation_code=str(row["Cód. Cotización"]),
            invoice_id=ConversionFilasExcel._optional_str(
                row["ID Factura"]
            ),
            payment_type=TipoDocumento(
                str(row["Tipo de Pago"])
            ),
            payment_entity=ConversionFilasExcel._optional_str(
                row["Entidad"]
            ),
            operation_number=ConversionFilasExcel._optional_str(
                row["N° Operación"]
            ),
            paid_amount=row["Monto Pagado"],
            currency=ConversionFilasExcel._optional_currency(
                row["Moneda"]
            ),
            payment_date=row["Fecha Pago"],
            verification_status=EstadoVerificacion(
                str(row["Estado Verificación"])
            ),
            reconciliation_status=EstadoVinculacionPago(
                str(row["Estado Conciliación"])
            ),
            source_hash=str(row["Hash Documento"]),
            source_files=ConversionFilasExcel._split(
                row["Archivos Origen"]
            ),
            duplicate_of=ConversionFilasExcel._split(
                row["Posible Duplicado De"]
            ),
            registered_at=(
                row["Fecha Registro"] or datetime.now()
            ),
            observations=ConversionFilasExcel._split(
                row["Acción / Observaciones"]
            ),
        )

    @staticmethod
    def _optional_str(value: object) -> str | None:
        return None if value in (None, "") else str(value)

    @staticmethod
    def _optional_currency(value: object) -> Moneda | None:
        return None if value in (None, "") else Moneda(str(value))

    @staticmethod
    def _optional_document_type(value: object) -> TipoDocumento | None:
        return None if value in (None, "") else TipoDocumento(str(value))

    @staticmethod
    def _split(value: object) -> list[str]:
        if value in (None, ""):
            return []
        return [part.strip() for part in str(value).split("|") if part.strip()]

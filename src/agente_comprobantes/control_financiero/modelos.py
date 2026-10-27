"""Contratos internos de control de operaciones de fletes.

Los campos nuevos están en español. No se modifican los contratos JSON
de extracción OCR ni los encabezados de los Excel existentes.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from pydantic import Field, field_validator

from agente_comprobantes.dominio.enumeraciones import Moneda
from agente_comprobantes.dominio.modelo_base import ModeloDominio


def importe_decimal(valor: object) -> Decimal:
    """Evita redondeos binarios y entradas monetarias ambiguas."""
    if isinstance(valor, (bool, float)) or valor is None:
        raise ValueError("Introduce un importe decimal como texto o Decimal.")
    try:
        importe = Decimal(str(valor).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("El importe no es un número decimal válido.") from exc
    if not importe.is_finite() or importe < 0:
        raise ValueError("El importe debe ser finito y no negativo.")
    return importe


def importe_positivo(valor: object) -> Decimal:
    importe = importe_decimal(valor)
    if importe == 0:
        raise ValueError("El importe debe ser mayor que cero.")
    return importe


class SituacionControl(StrEnum):
    CONFORME = "CONFORME"
    PENDIENTE = "PENDIENTE"
    OBSERVADA = "OBSERVADA"


class EvidenciaFinanciera(ModeloDominio):
    referencia: str | None = None
    documento_respaldo: str | None = None
    fecha: date | None = None
    moneda: Moneda
    verificada: bool = False


class MovimientoBancario(EvidenciaFinanciera):
    """Importe aplicado a esta factura; no necesariamente todo el movimiento."""
    importe_aplicado: Decimal

    @field_validator("importe_aplicado", mode="before")
    @classmethod
    def validar_importe(cls, valor: object) -> Decimal:
        return importe_positivo(valor)


class DeclaracionPagoPorAclarar(ModeloDominio):
    """Importe declarado que no constituye movimiento bancario acreditable."""

    referencia_original: str
    moneda: Moneda
    importe_declarado: Decimal
    respaldo_original: str | None = None

    @field_validator("importe_declarado", mode="before")
    @classmethod
    def validar_importe(cls, valor: object) -> Decimal:
        return importe_positivo(valor)


class DepositoDetraccion(EvidenciaFinanciera):
    """Depósito acreditado a la cuenta de detracciones del proveedor."""
    importe: Decimal

    @field_validator("importe", mode="before")
    @classmethod
    def validar_importe(cls, valor: object) -> Decimal:
        return importe_positivo(valor)


class NotaCredito(EvidenciaFinanciera):
    """Ajuste documentado aplicado a una factura determinada."""
    numero: str
    importe: Decimal

    @field_validator("importe", mode="before")
    @classmethod
    def validar_importe(cls, valor: object) -> Decimal:
        return importe_positivo(valor)


class RevisionExpediente(ModeloDominio):
    """Registro local de cambios; no representa una firma autenticada."""

    fecha: datetime
    motivo: str
    cambios: dict[str, str]


class DatosOrigenExcel(ModeloDominio):
    """Fotografía de los valores disponibles en la hoja importada.

    No se interpretan como acreditaciones ni sustituyen los documentos.
    """

    archivo: str | None = None
    huella_archivo: str
    hoja: str
    fila: int
    campos: dict[str, str] = Field(default_factory=dict)


class OperacionFlete(ModeloDominio):
    """Una operación corresponde a una única factura y su control de pagos.

    Si un movimiento bancario cubre varias facturas, registrar únicamente
    su importe asignado a esta factura y conservar la misma referencia externa.
    """
    identificador: str
    numero_factura: str
    moneda: Moneda
    monto_facturado: Decimal
    codigo_cotizacion: str | None = None
    monto_cotizado: Decimal | None = None
    numero_guia: str | None = None
    proveedor: str | None = None
    ruc_proveedor: str | None = None
    fecha_factura: date | None = None
    evidencia_factura: str | None = None
    detraccion_aplica: bool | None = None
    es_flete: bool | None = None
    movimientos_bancarios: list[MovimientoBancario] = Field(default_factory=list)
    declaraciones_por_aclarar: list[DeclaracionPagoPorAclarar] = Field(
        default_factory=list
    )
    depositos_detraccion: list[DepositoDetraccion] = Field(default_factory=list)
    notas_credito: list[NotaCredito] = Field(default_factory=list)
    conciliacion_cerrada: bool = False
    revisiones: list[RevisionExpediente] = Field(default_factory=list)
    datos_origen: DatosOrigenExcel | None = None

    @field_validator("monto_facturado", mode="before")
    @classmethod
    def validar_facturado(cls, valor: object) -> Decimal:
        return importe_positivo(valor)

    @field_validator("monto_cotizado", mode="before")
    @classmethod
    def validar_cotizado(cls, valor: object) -> Decimal | None:
        return None if valor is None else importe_decimal(valor)

    @field_validator("identificador", "numero_factura")
    @classmethod
    def validar_referencia(cls, valor: str) -> str:
        if not valor.strip():
            raise ValueError("La operación y la factura requieren identificador.")
        return valor

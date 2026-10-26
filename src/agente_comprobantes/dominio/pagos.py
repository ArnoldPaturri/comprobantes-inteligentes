from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import Field, field_validator

from agente_comprobantes.dominio.enumeraciones import (
    Moneda,
    TipoDocumento,
    EstadoVinculacionPago,
    EstadoVerificacion,
)
from agente_comprobantes.dominio.modelo_base import ModeloDominio
from agente_comprobantes.dominio.normalizacion import _parse_date, _parse_decimal


class RegistroPago(ModeloDominio):
    payment_id: str
    quotation_code: str
    invoice_id: str | None = None
    payment_type: TipoDocumento
    payment_entity: str | None = None
    operation_number: str | None = None
    paid_amount: Decimal | None = None
    currency: Moneda | None = None
    payment_date: date | None = None
    verification_status: EstadoVerificacion
    reconciliation_status: EstadoVinculacionPago = EstadoVinculacionPago.PENDING_INVOICE
    source_hash: str
    source_files: list[str]
    duplicate_of: list[str] = Field(default_factory=list)
    registered_at: datetime = Field(default_factory=datetime.now)
    observations: list[str] = Field(default_factory=list)

    _normalize_amount = field_validator("paid_amount", mode="before")(_parse_decimal)
    _normalize_date = field_validator("payment_date", mode="before")(_parse_date)

    @field_validator("quotation_code")
    @classmethod
    def normalize_quotation_code(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError(
                "El código de cotización del pago no puede estar vacío"
            )
        return normalized

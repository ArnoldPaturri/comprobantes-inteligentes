from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import Field, field_validator

from agente_comprobantes.dominio.enumeraciones import Moneda, EstadoCotizacion, EstadoVerificacion
from agente_comprobantes.dominio.modelo_base import ModeloDominio
from agente_comprobantes.dominio.normalizacion import _parse_date, _parse_decimal


class RegistroCotizacion(ModeloDominio):
    quotation_code: str
    provider: str | None = None
    provider_tax_id: str | None = None
    concept: str | None = None
    quoted_amount: Decimal | None = None
    currency: Moneda | None = None
    quotation_date: date | None = None
    status: EstadoCotizacion = EstadoCotizacion.WAITING_INVOICE
    verification_status: EstadoVerificacion
    source_hash: str
    source_files: list[str]
    uncertain_fields: list[str] = Field(default_factory=list)
    registered_at: datetime = Field(default_factory=datetime.now)
    observations: list[str] = Field(default_factory=list)

    _normalize_amount = field_validator("quoted_amount", mode="before")(_parse_decimal)
    _normalize_date = field_validator("quotation_date", mode="before")(_parse_date)

    @field_validator("quotation_code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("El código de cotización no puede estar vacío")
        return normalized

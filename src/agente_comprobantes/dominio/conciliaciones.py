from __future__ import annotations

from decimal import Decimal

from pydantic import Field, field_validator

from agente_comprobantes.dominio.enumeraciones import Diagnostico, EstadoPago
from agente_comprobantes.dominio.modelo_base import ModeloDominio
from agente_comprobantes.dominio.normalizacion import _parse_decimal
from agente_comprobantes.dominio.validacion import ObservacionValidacion


class ResultadoConciliacion(ModeloDominio):
    quoted_amount: Decimal | None
    invoiced_amount: Decimal | None
    difference: Decimal | None
    deviation_percent: Decimal | None
    diagnosis: Diagnostico
    provider_similarity: float | None = None
    issues: list[ObservacionValidacion] = Field(default_factory=list)

class ResultadoConciliacionPago(ModeloDominio):
    invoice_amount: Decimal | None
    previously_paid_amount: Decimal = Decimal("0")
    current_payment_amount: Decimal | None
    applied_amount: Decimal = Decimal("0")
    accumulated_paid_amount: Decimal = Decimal("0")
    remaining_amount: Decimal | None
    resulting_payment_status: EstadoPago
    applied: bool = True
    issues: list[ObservacionValidacion] = Field(default_factory=list)

    _normalize_invoice_amount = field_validator("invoice_amount", mode="before")(_parse_decimal)
    _normalize_previous_amount = field_validator(
        "previously_paid_amount", mode="before"
    )(_parse_decimal)
    _normalize_current_amount = field_validator(
        "current_payment_amount", mode="before"
    )(_parse_decimal)
    _normalize_applied_amount = field_validator("applied_amount", mode="before")(_parse_decimal)
    _normalize_accumulated_amount = field_validator(
        "accumulated_paid_amount", mode="before"
    )(_parse_decimal)
    _normalize_remaining_amount = field_validator("remaining_amount", mode="before")(
        _parse_decimal
    )

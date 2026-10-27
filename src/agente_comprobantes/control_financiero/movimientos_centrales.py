"""Modelos del registro bancario central y sus aplicaciones documentales."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator, model_validator

from agente_comprobantes.control_financiero.archivos import REFERENCIA
from agente_comprobantes.control_financiero.auditoria_importacion import (
    _referencias,
)
from agente_comprobantes.control_financiero.modelos import importe_positivo
from agente_comprobantes.control_financiero.tipos_referencia import (
    indicador_efectivo,
)
from agente_comprobantes.dominio.enumeraciones import Moneda
from agente_comprobantes.dominio.modelo_base import ModeloDominio


def _dinero(valor: object) -> Decimal:
    monto = importe_positivo(valor)
    if monto > Decimal("999999999999.99") or monto.as_tuple().exponent < -2:
        raise ValueError("Se requiere un importe con máximo dos decimales.")
    return monto


class AplicacionBancaria(ModeloDominio):
    """Importe propuesto para una factura; no es pago acreditado."""

    expediente: str
    importe: Decimal

    @field_validator("expediente")
    @classmethod
    def _expediente(cls, valor: str) -> str:
        if not valor:
            raise ValueError("La aplicación requiere un expediente.")
        return valor

    @field_validator("importe", mode="before")
    @classmethod
    def _importe(cls, valor: object) -> Decimal:
        return _dinero(valor)


class RevisionMovimientoCentral(ModeloDominio):
    """Decisión humana registrada sin afirmar confirmación bancaria."""

    fecha: datetime = Field(default_factory=lambda: datetime.now(UTC))
    accion: Literal[
        "VINCULAR_EVIDENCIA",
        "REDISTRIBUIR",
        "DOCUMENTAR",
        "REABRIR",
        "APLICAR",
        "REVERTIR_APLICACION",
    ]
    motivo: str
    cambios: dict[str, str] = Field(default_factory=dict)


class MovimientoBancarioCentral(ModeloDominio):
    """Un movimiento bancario y sus aplicaciones trazables a los expedientes."""

    identificador: str
    banco: str
    referencia: str
    moneda: Moneda
    importe_total: Decimal
    fecha_operacion: date | None = None
    aplicaciones: list[AplicacionBancaria] = Field(default_factory=list)
    sustento: str
    estado: Literal["BORRADOR", "DOCUMENTADO", "APLICADO", "REVERTIDO"] = "BORRADOR"
    respaldo: str | None = None
    revisiones: list[RevisionMovimientoCentral] = Field(default_factory=list)
    creado_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("identificador", "banco", "referencia")
    @classmethod
    def _no_vacio(cls, valor: str) -> str:
        if not valor.strip():
            raise ValueError("ID, banco y referencia son obligatorios.")
        return valor.strip()

    @field_validator("sustento")
    @classmethod
    def _motivo(cls, valor: str) -> str:
        if len(valor.strip()) < 10:
            raise ValueError("Indica el sustento del borrador (mínimo 10 caracteres).")
        return valor.strip()

    @field_validator("referencia")
    @classmethod
    def _referencia_individual(cls, valor: str) -> str:
        if indicador_efectivo(valor) or len(_referencias(valor)) != 1:
            raise ValueError("Se exige una referencia bancaria individual, no EFECTIVO.")
        return valor

    @field_validator("importe_total", mode="before")
    @classmethod
    def _importe(cls, valor: object) -> Decimal:
        return _dinero(valor)

    @model_validator(mode="after")
    def _validar_total(self) -> MovimientoBancarioCentral:
        if self.moneda == Moneda.OTHER:
            raise ValueError("La moneda del movimiento debe ser PEN, USD o EUR.")
        ids = [item.expediente.casefold() for item in self.aplicaciones]
        if len(ids) != len(set(ids)):
            raise ValueError("Una factura no puede recibir dos aplicaciones del mismo movimiento.")
        if sum((item.importe for item in self.aplicaciones), Decimal("0")) > self.importe_total:
            raise ValueError("La suma asignada supera el importe total del voucher.")
        if not self.aplicaciones:
            raise ValueError("El borrador requiere al menos una aplicación.")
        if self.respaldo is not None and not REFERENCIA.fullmatch(self.respaldo):
            raise ValueError("El respaldo central debe ser un adjunto interno válido.")
        if self.estado in ("DOCUMENTADO", "APLICADO", "REVERTIDO") and not self.respaldo:
            raise ValueError("No se puede documentar un movimiento sin voucher adjunto.")
        return self

    @property
    def sin_asignar(self) -> Decimal:
        return self.importe_total - sum(
            (item.importe for item in self.aplicaciones), Decimal("0")
        )

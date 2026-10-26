"""Modelos del dominio reexportados desde módulos especializados."""

from agente_comprobantes.dominio.conciliaciones import (
    ResultadoConciliacion,
    ResultadoConciliacionPago,
)
from agente_comprobantes.dominio.cotizaciones import RegistroCotizacion
from agente_comprobantes.dominio.extraccion import ExtraccionDocumento
from agente_comprobantes.dominio.facturas import RegistroFactura
from agente_comprobantes.dominio.modelo_base import ModeloDominio
from agente_comprobantes.dominio.pagos import RegistroPago
from agente_comprobantes.dominio.referencias import CoincidenciaDuplicado, ReferenciaDocumento
from agente_comprobantes.dominio.resultados import ResultadoRegistro, ResultadoVinculacionPago
from agente_comprobantes.dominio.validacion import InformeValidacion, ObservacionValidacion

__all__ = [
    "ModeloDominio",
    "ExtraccionDocumento",
    "ObservacionValidacion",
    "InformeValidacion",
    "CoincidenciaDuplicado",
    "ReferenciaDocumento",
    "ResultadoConciliacion",
    "ResultadoConciliacionPago",
    "RegistroCotizacion",
    "RegistroFactura",
    "RegistroPago",
    "ResultadoRegistro",
    "ResultadoVinculacionPago",
]

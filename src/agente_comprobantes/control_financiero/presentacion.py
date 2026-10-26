"""Datos de consulta para el dashboard, sin modificar registros operativos."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from agente_comprobantes.control_financiero.conciliacion import (
    ResultadoControlFlete,
    conciliar_flete,
)
from agente_comprobantes.control_financiero.modelos import (
    OperacionFlete,
    SituacionControl,
)
from agente_comprobantes.control_financiero.repositorio_json import (
    RepositorioControlFletes,
)
from agente_comprobantes.control_financiero.resumen import ResumenMoneda, resumir_operaciones
from agente_comprobantes.dominio.enumeraciones import Moneda


@dataclass(frozen=True, slots=True)
class FilaPanelFlete:
    identificador: str
    factura: str
    proveedor: str
    guia: str
    clasificacion: str
    moneda: Moneda
    facturado: Decimal
    declarado: Decimal
    acreditado: Decimal
    saldo_documental: Decimal
    situacion: SituacionControl


@dataclass(frozen=True, slots=True)
class TableroFletes:
    operaciones: list[OperacionFlete]
    resultados: dict[str, ResultadoControlFlete]
    resumenes: list[ResumenMoneda]

    def filas(
        self,
        moneda: Moneda | None = None,
        situacion: SituacionControl | None = None,
        busqueda: str = "",
    ) -> list[FilaPanelFlete]:
        filtro = busqueda.strip().casefold()
        filas: list[FilaPanelFlete] = []
        for operacion in self.operaciones:
            estado = self.resultados[operacion.identificador]
            if moneda is not None and operacion.moneda != moneda:
                continue
            if situacion is not None and estado.situacion != situacion:
                continue
            campos = (
                operacion.identificador,
                operacion.numero_factura,
                operacion.proveedor or "",
                operacion.numero_guia or "",
                operacion.codigo_cotizacion or "",
            )
            if filtro and not any(filtro in campo.casefold() for campo in campos):
                continue
            declarado = sum(
                (pago.importe_aplicado for pago in operacion.movimientos_bancarios),
                Decimal("0"),
            )
            filas.append(
                FilaPanelFlete(
                    identificador=operacion.identificador,
                    factura=operacion.numero_factura,
                    proveedor=operacion.proveedor or "Sin proveedor",
                    guia=operacion.numero_guia or "Por asociar",
                    clasificacion=(
                        "Flete" if operacion.es_flete is True
                        else "Otro servicio" if operacion.es_flete is False
                        else "Sin clasificar"
                    ),
                    moneda=operacion.moneda,
                    facturado=estado.facturado_neto,
                    declarado=declarado,
                    acreditado=estado.total_acreditado,
                    saldo_documental=estado.saldo_por_acreditar,
                    situacion=estado.situacion,
                )
            )
        return filas


def construir_tablero(operaciones: list[OperacionFlete]) -> TableroFletes:
    resultados = {
        operacion.identificador: conciliar_flete(operacion)
        for operacion in operaciones
    }
    if len(resultados) != len(operaciones):
        raise ValueError("Existen identificadores de control duplicados.")
    return TableroFletes(
        operaciones=operaciones,
        resultados=resultados,
        resumenes=resumir_operaciones(
            [operacion for operacion in operaciones if operacion.es_flete is True]
        ),
    )


def cargar_tablero(ruta: str | Path) -> TableroFletes:
    """Lectura exclusivamente; no llama al proveedor OCR ni escribe archivos."""
    return construir_tablero(RepositorioControlFletes(ruta).listar())


def formatear_importe(importe: Decimal, moneda: Moneda) -> str:
    simbolo = {Moneda.PEN: "S/", Moneda.USD: "US$", Moneda.EUR: "€"}
    signo = simbolo.get(moneda, moneda.value)
    return f"{signo} {importe:,.2f}"

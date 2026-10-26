"""Consolidado financiero sin sumar dos veces un mismo presupuesto."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from pydantic import Field

from agente_comprobantes.control_financiero.conciliacion import conciliar_flete
from agente_comprobantes.control_financiero.modelos import (
    OperacionFlete,
    SituacionControl,
)
from agente_comprobantes.dominio.enumeraciones import Moneda
from agente_comprobantes.dominio.modelo_base import ModeloDominio


class ResumenMoneda(ModeloDominio):
    moneda: Moneda
    total_presupuestado: Decimal = Decimal("0")
    facturado_con_presupuesto: Decimal = Decimal("0")
    facturado_sin_presupuesto: Decimal = Decimal("0")
    desviacion_neta_presupuestada: Decimal = Decimal("0")
    exceso_acumulado_presupuesto: Decimal = Decimal("0")
    cantidad_conformes: int = 0
    cantidad_pendientes: int = 0
    cantidad_observadas: int = 0
    cantidad_sin_presupuesto: int = 0
    presupuestos_incompletos: list[str] = Field(default_factory=list)


def resumir_operaciones(operaciones: list[OperacionFlete]) -> list[ResumenMoneda]:
    """Agrupa por divisa y cotización, sin duplicar presupuestos.

    'Exceso acumulado' es una medida provisional: no constituye por sí
    solo una auditoría tributaria ni confirma sobrecostos aprobados.
    Una factura sin cotización se informa aparte, nunca se compara con cero.
    """
    vistos: set[tuple[str, str, str]] = set()
    por_moneda: dict[Moneda, ResumenMoneda] = {}
    presupuestos: dict[tuple[Moneda, str], Decimal] = {}
    acumulados: dict[tuple[Moneda, str], Decimal] = defaultdict(Decimal)
    codigos_incompletos: dict[Moneda, set[str]] = defaultdict(set)

    for op in operaciones:
        clave_factura = (
            (op.ruc_proveedor or op.proveedor or "").strip().upper(),
            op.numero_factura.strip().upper(),
            op.moneda.value,
        )
        if clave_factura in vistos:
            raise ValueError(
                "Hay una factura repetida en el consolidado: "
                f"{op.numero_factura} ({op.moneda.value})."
            )
        vistos.add(clave_factura)

        resumen = por_moneda.setdefault(op.moneda, ResumenMoneda(moneda=op.moneda))
        resultado = conciliar_flete(op)
        if resultado.situacion == SituacionControl.CONFORME:
            resumen.cantidad_conformes += 1
        elif resultado.situacion == SituacionControl.OBSERVADA:
            resumen.cantidad_observadas += 1
        else:
            resumen.cantidad_pendientes += 1

        if not op.codigo_cotizacion:
            resumen.facturado_sin_presupuesto += resultado.facturado_neto
            resumen.cantidad_sin_presupuesto += 1
            continue

        codigo = op.codigo_cotizacion.strip().upper()
        clave_cotizacion = (op.moneda, codigo)
        acumulados[clave_cotizacion] += resultado.facturado_neto

        if op.monto_cotizado is None:
            codigos_incompletos[op.moneda].add(codigo)
        elif clave_cotizacion in presupuestos:
            if presupuestos[clave_cotizacion] != op.monto_cotizado:
                raise ValueError(
                    "Un mismo código de cotización tiene presupuestos distintos: "
                    f"{codigo} ({op.moneda.value})."
                )
        else:
            presupuestos[clave_cotizacion] = op.monto_cotizado

    for (moneda, codigo), importe in acumulados.items():
        resumen = por_moneda[moneda]
        presupuesto = presupuestos.get((moneda, codigo))
        if presupuesto is None:
            resumen.facturado_sin_presupuesto += importe
            resumen.cantidad_sin_presupuesto += 1
            codigos_incompletos[moneda].add(codigo)
            continue
        resumen.total_presupuestado += presupuesto
        resumen.facturado_con_presupuesto += importe
        diferencia = importe - presupuesto
        resumen.desviacion_neta_presupuestada += diferencia
        if diferencia > 0:
            resumen.exceso_acumulado_presupuesto += diferencia

    for moneda, resumen in por_moneda.items():
        resumen.presupuestos_incompletos = sorted(codigos_incompletos[moneda])

    return [por_moneda[m] for m in sorted(por_moneda, key=lambda m: m.value)]

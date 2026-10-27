"""Propuesta NO vinculante de agrupación por factura en vista previa.

Agrupa filas solo para análisis. Conserva referencias e importes tal como
aparecen en la hoja, sin distribuir ni acreditar movimientos bancarios.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from agente_comprobantes.control_financiero.auditoria_importacion import (
    _campo,
    _referencias,
)
from agente_comprobantes.control_financiero.importacion_masiva import (
    VistaPrevia,
    _importe,
    _normalizar,
)


@dataclass(frozen=True, slots=True)
class PropuestaAgrupacion:
    factura: str
    proveedor: str
    moneda: str
    filas: tuple[int, ...]
    referencias_originales: tuple[str, ...]
    facturado_referencia: Decimal | None
    pagos_declarados: Decimal
    condicion: str
    observaciones: tuple[str, ...]


def proponer_agrupaciones(vista: VistaPrevia) -> tuple[PropuestaAgrupacion, ...]:
    """Resume facturas repetidas sin transformarlas en expedientes guardables."""
    grupos = defaultdict(list)
    for fila in vista.filas:
        if fila.estado not in {"LISTA", "DUPLICADA"}:
            continue
        clave = (_normalizar(fila.factura), _normalizar(fila.proveedor))
        grupos[clave].append(fila)

    resultado = []
    for filas in grupos.values():
        if len(filas) < 2:
            continue
        primera = filas[0]
        monedas = {f.moneda for f in filas}
        referencias = []
        montos_facturados = set()
        pagos = []
        observaciones = []
        repetidas: set[str] = set()
        vistos: set[str] = set()
        for fila in filas:
            raw = fila.valores_origen
            referencia = _campo(raw, "referencia")
            referencias.append(referencia)
            partes = _referencias(referencia)
            if len(partes) != 1:
                observaciones.append(
                    f"Fila {fila.fila}: referencia ausente o múltiple."
                )
            else:
                if partes[0] in vistos:
                    repetidas.add(partes[0])
                vistos.add(partes[0])
            try:
                montos_facturados.add(_importe(_campo(raw, "facturado")))
                texto_pago = _campo(raw, "pago")
                pagos.append(
                    _importe(texto_pago, permitir_cero=True)
                    if texto_pago else Decimal("0")
                )
            except ValueError:
                observaciones.append(
                    f"Fila {fila.fila}: importe no conciliable."
                )
        if len(monedas) > 1:
            observaciones.append("La factura aparece con monedas distintas.")
        if len(montos_facturados) > 1:
            observaciones.append(
                "El importe facturado difiere entre las filas."
            )
        if repetidas:
            observaciones.append(
                "Una referencia se repite dentro de la misma factura."
            )
        facturado = (
            next(iter(montos_facturados))
            if len(montos_facturados) == 1 else None
        )
        total_pago = sum(pagos, Decimal("0"))
        if facturado is not None and total_pago > facturado:
            observaciones.append(
                "La suma declarada de pagos excede el importe de la factura."
            )
        condicion = (
            "CANDIDATA A REVISIÓN"
            if not observaciones else "REQUIERE ACLARACIÓN"
        )
        resultado.append(
            PropuestaAgrupacion(
                factura=primera.factura,
                proveedor=primera.proveedor,
                moneda=primera.moneda if len(monedas) == 1 else "VARIAS",
                filas=tuple(f.fila for f in filas),
                referencias_originales=tuple(referencias),
                facturado_referencia=facturado,
                pagos_declarados=total_pago,
                condicion=condicion,
                observaciones=tuple(observaciones),
            )
        )
    return tuple(sorted(resultado, key=lambda x: x.filas[0]))

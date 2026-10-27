"""Auditoría previa de referencias y conciliación, exclusivamente de lectura.

No divide movimientos multipago ni asigna bancarizaciones a facturas.
Una situación ambigua bloquea la importación hasta definir una regla
explícita de asignación y reconciliación.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from agente_comprobantes.control_financiero.importacion_masiva import (
    ALIAS,
    VistaPrevia,
    _importe,
    _normalizar,
)
from agente_comprobantes.control_financiero.tipos_referencia import (
    efectivo_por_confirmar,
    indicador_efectivo,
)


@dataclass(frozen=True, slots=True)
class HallazgoImportacion:
    codigo: str
    filas: tuple[int, ...]
    detalle: str
    bloquea: bool = True


@dataclass(frozen=True, slots=True)
class AuditoriaImportacion:
    hallazgos: tuple[HallazgoImportacion, ...]

    @property
    def bloquea_importacion(self) -> bool:
        return any(item.bloquea for item in self.hallazgos)


def _campo(origen: dict[str, str], campo: str) -> str:
    for encabezado, valor in origen.items():
        if ALIAS.get(_normalizar(encabezado)) == campo:
            return valor.strip()
    return ""


def normalizar_referencia_para_busqueda(valor: str) -> str:
    """Normaliza .0 en referencias numéricas SIN modificar el dato original."""
    referencia = valor.strip()
    if re.fullmatch(r"\d+\.0+", referencia):
        return referencia.split(".", maxsplit=1)[0]
    return referencia.upper()


def _referencias(valor: str) -> list[str]:
    if not valor.strip():
        return []
    return [
        normalizar_referencia_para_busqueda(parte)
        for parte in re.split(r"\s+(?:Y|E|AND)\s+|[;,]", valor, flags=re.IGNORECASE)
        if parte.strip()
    ]


def auditar_importacion(vista: VistaPrevia) -> AuditoriaImportacion:
    """Inspecciona las filas del Excel sin modificar operaciones ni pagos."""
    agrupadas: dict[str, list[int]] = defaultdict(list)
    referencias: dict[str, dict[str, list[int]]] = defaultdict(
        lambda: defaultdict(list)
    )
    hallazgos: list[HallazgoImportacion] = []

    for fila in vista.filas:
        if fila.estado not in {"LISTA", "DUPLICADA"}:
            continue
        clave = f"{_normalizar(fila.factura)}|{_normalizar(fila.proveedor)}"
        agrupadas[clave].append(fila.fila)
        raw = fila.valores_origen
        etiqueta = _campo(raw, "referencia")
        if indicador_efectivo(etiqueta):
            incierto = efectivo_por_confirmar(etiqueta)
            hallazgos.append(
                HallazgoImportacion(
                    "EFECTIVO_POR_CONFIRMAR" if incierto else "EFECTIVO_SIN_OPERACION",
                    (fila.fila,),
                    (
                        "La celda dice EFECTIVO? y requiere aclarar el medio de pago. "
                        "No es una referencia bancaria."
                        if incierto else
                        "La celda dice EFECTIVO, pero no identifica una operación "
                        "bancaria. Revisar el sustento del pago."
                    ),
                    bloquea=False,
                )
            )
            identificadores = []
        else:
            identificadores = _referencias(etiqueta)
        if len(identificadores) > 1:
            hallazgos.append(
                HallazgoImportacion(
                    "REFERENCIAS_MULTIPLES",
                    (fila.fila,),
                    "Una celda incluye varias referencias de bancarización. "
                    "No se puede distribuir automáticamente el importe entre ellas.",
                )
            )
        for ref in set(identificadores):
            referencias[ref][clave].append(fila.fila)

        monto_facturado = _campo(raw, "facturado")
        monto_pagado = _campo(raw, "pago")
        monto_diferencia = _campo(raw, "diferencia")
        if monto_facturado and monto_pagado and monto_diferencia:
            try:
                esperado = _importe(monto_facturado) - _importe(
                    monto_pagado, permitir_cero=True
                )
                declarado = _importe(monto_diferencia, permitir_cero=True)
            except ValueError:
                continue
            if abs(esperado - declarado) > 0.01:
                hallazgos.append(
                    HallazgoImportacion(
                        "DIFERENCIA_POR_REVISAR",
                        (fila.fila,),
                        "La diferencia original no coincide con Facturado menos "
                        "Bancarizado. Puede responder a detracciones, notas de "
                        "crédito u otras reglas aún no automatizadas.",
                        bloquea=False,
                    )
                )

    for numeros in agrupadas.values():
        if len(numeros) > 1:
            hallazgos.append(
                HallazgoImportacion(
                    "FACTURA_EN_VARIAS_FILAS",
                    tuple(sorted(numeros)),
                    "Una misma factura y proveedor aparecen en varias filas. "
                    "No debe perderse ningún pago por deduplicación automática.",
                )
            )

    for referencia, grupos in referencias.items():
        if len(grupos) > 1:
            filas = tuple(sorted({n for nums in grupos.values() for n in nums}))
            hallazgos.append(
                HallazgoImportacion(
                    "REFERENCIA_COMPARTIDA",
                    filas,
                    f"La referencia {referencia} aparece en diferentes facturas. "
                    "Debe verificarse la distribución del pago antes de importar.",
                )
            )
    return AuditoriaImportacion(
        tuple(sorted(hallazgos, key=lambda item: (item.filas[0], item.codigo)))
    )

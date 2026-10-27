"""Edición conservadora de incidencias en expedientes ya registrados.

Se permite preparar desgloses de importes DECLARADOS y reclasificar marcas
de efectivo. Nunca se acreditan pagos, no se borra el origen y todo cambio
requiere confirmación, sustento y revisión de versión.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from agente_comprobantes.control_financiero.auditoria_importacion import (
    _referencias,
)
from agente_comprobantes.control_financiero.modelos import (
    DeclaracionPagoPorAclarar,
    MovimientoBancario,
    OperacionFlete,
    RevisionExpediente,
)
from agente_comprobantes.control_financiero.repositorio_json import (
    RepositorioControlFletes,
)
from agente_comprobantes.control_financiero.tipos_referencia import (
    indicador_efectivo,
)

DOS_DECIMALES = Decimal("0.01")


def _validar_sustento(
    operacion: OperacionFlete,
    *,
    motivo: str,
    confirmacion: bool,
    version_esperada: int,
) -> str:
    if len(operacion.revisiones) != version_esperada:
        raise ValueError("El expediente cambió; vuelve a cargar los datos.")
    if not confirmacion or len(motivo.strip()) < 10:
        raise ValueError("Confirma los datos e indica un sustento de al menos 10 caracteres.")
    return motivo.strip()


def _seleccionar_pago(operacion: OperacionFlete, indice: int) -> MovimientoBancario:
    if isinstance(indice, bool) or not isinstance(indice, int):
        raise ValueError("La posición del movimiento debe ser entera.")
    if not 0 <= indice < len(operacion.movimientos_bancarios):
        raise ValueError("El movimiento seleccionado no existe.")
    pago = operacion.movimientos_bancarios[indice]
    if pago.verificada:
        raise ValueError(
            "Primero retira la acreditación documental existente desde Revisar pagos."
        )
    if operacion.conciliacion_cerrada:
        raise ValueError("Primero reabre la conciliación antes de modificar el pago.")
    return pago


def _monto(valor: str | Decimal) -> Decimal:
    if isinstance(valor, float) or isinstance(valor, bool):
        raise ValueError("Los importes deben ingresarse como texto decimal.")
    try:
        monto = Decimal(str(valor).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Importe inválido.") from exc
    if (
        not monto.is_finite()
        or monto <= 0
        or monto > Decimal("999999999999.99")
        or monto != monto.quantize(DOS_DECIMALES)
    ):
        raise ValueError("Importe positivo con máximo dos decimales requerido.")
    return monto


def preparar_desglose(
    operacion: OperacionFlete,
    *,
    indice: int,
    asignaciones: list[tuple[str, str]],
    motivo: str,
    confirmacion: bool,
    version_esperada: int,
    otras_operaciones: list[OperacionFlete] | None = None,
) -> OperacionFlete:
    sustento = _validar_sustento(
        operacion, motivo=motivo, confirmacion=confirmacion,
        version_esperada=version_esperada,
    )
    anterior = _seleccionar_pago(operacion, indice)
    original = anterior.referencia or ""
    separadas = _referencias(original)
    if len(separadas) < 2:
        raise ValueError("La referencia original no contiene múltiples operaciones.")
    if len(set(separadas)) != len(separadas):
        raise ValueError("La referencia de origen contiene identificadores repetidos.")
    if len(asignaciones) != len(separadas):
        raise ValueError("Se requiere un importe por cada referencia original.")
    if anterior.moneda != operacion.moneda:
        raise ValueError("La moneda del pago no coincide con la de la factura.")
    refs = [referencia.strip().upper() for referencia, _ in asignaciones]
    if any(
        not re.fullmatch(r"[A-Z0-9][A-Z0-9./_-]{1,49}", ref)
        or indicador_efectivo(ref) for ref in refs
    ):
        raise ValueError("Usa referencias individuales de operación válidas.")
    if len(set(refs)) != len(refs) or set(refs) != set(separadas):
        raise ValueError(
            "Las referencias deben coincidir exactamente con las originales, "
            "sin añadir, omitir ni repetir."
        )
    importes = [_monto(importe) for _, importe in asignaciones]
    if sum(importes, Decimal("0")) != anterior.importe_aplicado:
        raise ValueError(
            "La suma de importes debe coincidir exactamente con el pago declarado."
        )
    for op in otras_operaciones or []:
        if op.identificador == operacion.identificador:
            continue
        for movimiento in op.movimientos_bancarios:
            usados = _referencias(movimiento.referencia or "")
            if set(refs) & set(usados):
                raise ValueError(
                    "Una referencia ya figura en otra factura. "
                    "Primero revisa la posible distribución del pago."
                )

    desglosados = [
        MovimientoBancario(
            moneda=anterior.moneda,
            referencia=ref,
            importe_aplicado=importe,
            documento_respaldo=None,
            fecha=anterior.fecha,
            verificada=False,
        )
        for ref, importe in zip(refs, importes, strict=True)
    ]
    datos = operacion.model_dump(mode="python")
    datos["movimientos_bancarios"] = [
        *datos["movimientos_bancarios"][:indice],
        *(mov.model_dump(mode="python") for mov in desglosados),
        *datos["movimientos_bancarios"][indice + 1:],
    ]
    datos["conciliacion_cerrada"] = False
    datos["revisiones"] = [
        *operacion.revisiones,
        RevisionExpediente(
            fecha=datetime.now(UTC),
            motivo=sustento,
            cambios={
                "accion": "desglose_declarado",
                "referencia_original": original,
                "importe_original": str(anterior.importe_aplicado),
                "indice_original": str(indice),
                "referencias_nuevas": " | ".join(
                    f"{ref}={importe}" for ref, importe in zip(refs, importes, strict=True)
                ),
                "respaldo_previo": anterior.documento_respaldo or "",
                "acreditado": "False",
            },
        ),
    ]
    return OperacionFlete.model_validate(datos)


def preparar_reclasificacion_efectivo(
    operacion: OperacionFlete,
    *,
    indice: int,
    motivo: str,
    confirmacion: bool,
    version_esperada: int,
) -> OperacionFlete:
    sustento = _validar_sustento(
        operacion, motivo=motivo, confirmacion=confirmacion,
        version_esperada=version_esperada,
    )
    anterior = _seleccionar_pago(operacion, indice)
    if not indicador_efectivo(anterior.referencia):
        raise ValueError("El movimiento seleccionado no tiene una etiqueta de efectivo.")
    datos = operacion.model_dump(mode="python")
    datos["movimientos_bancarios"].pop(indice)
    pendiente = DeclaracionPagoPorAclarar(
        referencia_original=anterior.referencia or "",
        moneda=anterior.moneda,
        importe_declarado=anterior.importe_aplicado,
        respaldo_original=anterior.documento_respaldo,
    )
    datos["declaraciones_por_aclarar"] = [
        *operacion.declaraciones_por_aclarar,
        pendiente,
    ]
    datos["conciliacion_cerrada"] = False
    datos["revisiones"] = [
        *operacion.revisiones,
        RevisionExpediente(
            fecha=datetime.now(UTC),
            motivo=sustento,
            cambios={
                "accion": "reclasificar_efectivo",
                "referencia_original": anterior.referencia or "",
                "importe_declarado": str(anterior.importe_aplicado),
                "moneda": anterior.moneda.value,
                "respaldo_previo": anterior.documento_respaldo or "",
                "acreditado": "False",
            },
        ),
    ]
    return OperacionFlete.model_validate(datos)


def guardar_desglose(
    repositorio: RepositorioControlFletes,
    identificador: str,
    *,
    indice: int,
    asignaciones: list[tuple[str, str]],
    motivo: str,
    confirmacion: bool,
    version_esperada: int,
) -> OperacionFlete:
    operaciones = repositorio.listar()
    actual = next(
        (op for op in operaciones if op.identificador == identificador),
        None,
    )
    if actual is None:
        raise ValueError("El expediente no existe.")
    nuevo = preparar_desglose(
        actual,
        indice=indice,
        asignaciones=asignaciones,
        motivo=motivo,
        confirmacion=confirmacion,
        version_esperada=version_esperada,
        otras_operaciones=operaciones,
    )
    repositorio.actualizar(nuevo)
    return nuevo


def guardar_reclasificacion_efectivo(
    repositorio: RepositorioControlFletes,
    identificador: str,
    *,
    indice: int,
    motivo: str,
    confirmacion: bool,
    version_esperada: int,
) -> OperacionFlete:
    actual = repositorio.obtener(identificador)
    if actual is None:
        raise ValueError("El expediente no existe.")
    nuevo = preparar_reclasificacion_efectivo(
        actual,
        indice=indice,
        motivo=motivo,
        confirmacion=confirmacion,
        version_esperada=version_esperada,
    )
    repositorio.actualizar(nuevo)
    return nuevo

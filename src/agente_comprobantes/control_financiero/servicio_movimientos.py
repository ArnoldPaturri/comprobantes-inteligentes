"""Servicio de aplicaciones bancarias, todavía sin impacto en conciliación."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from agente_comprobantes.control_financiero.archivos import AlmacenAdjuntos, preparar_adjunto
from agente_comprobantes.control_financiero.auditoria_importacion import (
    _referencias,
)
from agente_comprobantes.control_financiero.modelos import (
    MovimientoBancario,
    OperacionFlete,
    RevisionExpediente,
)
from agente_comprobantes.control_financiero.movimientos_centrales import (
    AplicacionBancaria,
    MovimientoBancarioCentral,
    RevisionMovimientoCentral,
)
from agente_comprobantes.control_financiero.repositorio_json import (
    RepositorioControlFletes,
)
from agente_comprobantes.control_financiero.repositorio_movimientos import (
    RepositorioMovimientosCentrales,
)
from agente_comprobantes.dominio.enumeraciones import Moneda


def preparar_borrador_central(
    *,
    banco: str,
    referencia: str,
    moneda: Moneda,
    importe_total: str,
    aplicaciones: list[tuple[str, str]],
    sustento: str,
    facturas: list[OperacionFlete],
    previos: list[MovimientoBancarioCentral],
    fecha_operacion: date | None = None,
    identificador: str | None = None,
) -> MovimientoBancarioCentral:
    """Comprobar saldos declarados y referencias sin tocar registros existentes."""
    borrador = MovimientoBancarioCentral(
        identificador=identificador or "MB-" + uuid4().hex[:12].upper(),
        banco=banco,
        referencia=referencia,
        moneda=moneda,
        importe_total=importe_total,
        fecha_operacion=fecha_operacion,
        aplicaciones=[
            AplicacionBancaria(expediente=ref, importe=importe)
            for ref, importe in aplicaciones
        ],
        sustento=sustento,
    )
    objetivo = _referencias(borrador.referencia)[0]
    for expediente in facturas:
        for pago in expediente.movimientos_bancarios:
            if (pago.movimiento_central_id != borrador.identificador\n                    and objetivo in _referencias(pago.referencia or "")):
                raise ValueError(
                    "La referencia ya está presente en un expediente histórico. "
                    "Primero revisa el registro existente; no crees otro pago."
                )
    for movimiento in previos:
        if objetivo in _referencias(movimiento.referencia):
            raise ValueError(
                "La referencia ya existe en el registro central de borradores."
            )

    por_id = {factura.identificador: factura for factura in facturas}
    for aplicacion in borrador.aplicaciones:
        factura = por_id.get(aplicacion.expediente)
        if factura is None:
            raise ValueError(f"No existe la factura {aplicacion.expediente}.")
        if factura.moneda != borrador.moneda:
            raise ValueError("Las aplicaciones deben usar la misma moneda del voucher.")
        prev_borradores = sum(
            (
                item.importe
                for movimiento in previos
                for item in movimiento.aplicaciones
                if item.expediente == factura.identificador
            ),
            Decimal("0"),
        )
        declarado = sum(
            (pago.importe_aplicado for pago in factura.movimientos_bancarios),
            Decimal("0"),
        )
        disponible = factura.monto_facturado - declarado - prev_borradores
        if aplicacion.importe > disponible:
            raise ValueError(
                "La asignación excede el saldo sin pagos ya declarados para "
                f"la factura {factura.numero_factura}. Revisa sus registros previos."
            )
    return borrador


def guardar_borrador_central(
    banco_repo: RepositorioMovimientosCentrales,
    control_repo: RepositorioControlFletes,
    *,
    banco: str,
    referencia: str,
    moneda: Moneda,
    importe_total: str,
    aplicaciones: list[tuple[str, str]],
    sustento: str,
    huella_control: str,
    huella_central: str,
    fecha_operacion: date | None = None,
) -> MovimientoBancarioCentral:
    """Crear borrador en archivo separado; nunca modifica los saldos oficiales."""
    if control_repo.huella() != huella_control:
        raise ValueError("Los expedientes cambiaron; recarga antes de guardar.")
    if banco_repo.huella() != huella_central:
        raise ValueError("El registro central cambió; recarga antes de guardar.")
    borrador = preparar_borrador_central(
        banco=banco,
        referencia=referencia,
        moneda=moneda,
        importe_total=importe_total,
        aplicaciones=aplicaciones,
        sustento=sustento,
        facturas=control_repo.listar(),
        previos=banco_repo.listar(),
        fecha_operacion=fecha_operacion,
    )
    if control_repo.huella() != huella_control:
        raise ValueError("Los expedientes cambiaron durante la revisión.")
    banco_repo.agregar(borrador, huella_esperada=huella_central)
    return borrador


def _validar_versiones(
    banco_repo: RepositorioMovimientosCentrales,
    control_repo: RepositorioControlFletes,
    huella_central: str,
    huella_control: str,
) -> None:
    if banco_repo.huella() != huella_central:
        raise ValueError("El registro central cambió; vuelve a revisar.")
    if control_repo.huella() != huella_control:
        raise ValueError("Los expedientes cambiaron; vuelve a revisar.")


def _revision(accion: str, motivo: str, cambios: dict[str, str]) -> RevisionMovimientoCentral:
    motivo = motivo.strip()
    if len(motivo) < 10:
        raise ValueError("El motivo de revisión requiere al menos diez caracteres.")
    return RevisionMovimientoCentral(accion=accion, motivo=motivo, cambios=cambios)


def _cotejar_distribucion(
    actual: MovimientoBancarioCentral,
    facturas: list[OperacionFlete],
    previos: list[MovimientoBancarioCentral],
    aplicaciones: list[tuple[str, str]],
) -> list[AplicacionBancaria]:
    borrador = preparar_borrador_central(
        banco=actual.banco,
        referencia=actual.referencia,
        moneda=actual.moneda,
        importe_total=str(actual.importe_total),
        aplicaciones=aplicaciones,
        sustento=actual.sustento,
        fecha_operacion=actual.fecha_operacion,
        facturas=facturas,
        previos=[
            item for item in previos if item.identificador != actual.identificador
        ],
    )
    return borrador.aplicaciones


def redistribuir_movimiento_central(
    banco_repo: RepositorioMovimientosCentrales,
    control_repo: RepositorioControlFletes,
    identificador: str,
    *,
    aplicaciones: list[tuple[str, str]],
    motivo: str,
    confirmacion: bool,
    huella_central: str,
    huella_control: str,
) -> MovimientoBancarioCentral:
    """Corrige aplicaciones de un borrador sin generar otro movimiento."""
    if not confirmacion:
        raise ValueError("Confirma la redistribución revisada.")
    _validar_versiones(banco_repo, control_repo, huella_central, huella_control)
    movimientos = banco_repo.listar()
    actual = next((m for m in movimientos if m.identificador == identificador), None)
    if actual is None:
        raise ValueError("No existe el movimiento central.")
    if actual.estado != "BORRADOR":
        raise ValueError("Un movimiento documentado no puede redistribuirse.")
    revisadas = _cotejar_distribucion(
        actual, control_repo.listar(), movimientos, aplicaciones
    )
    if revisadas == actual.aplicaciones:
        raise ValueError("La distribución no presenta cambios.")
    revision = _revision(
        "REDISTRIBUIR",
        motivo,
        {
            "anterior": ", ".join(
                f"{a.expediente}:{a.importe}" for a in actual.aplicaciones
            ),
            "nuevo": ", ".join(
                f"{a.expediente}:{a.importe}" for a in revisadas
            ),
        },
    )
    cambiado = actual.model_copy(update={
        "aplicaciones": revisadas,
        "revisiones": [*actual.revisiones, revision],
    })
    _validar_versiones(banco_repo, control_repo, huella_central, huella_control)
    banco_repo.actualizar(cambiado, huella_esperada=huella_central)
    return cambiado


def adjuntar_voucher_central(
    banco_repo: RepositorioMovimientosCentrales,
    control_repo: RepositorioControlFletes,
    almacen: AlmacenAdjuntos,
    identificador: str,
    *,
    nombre: str,
    contenido: bytes,
    motivo: str,
    confirmacion: bool,
    huella_central: str,
    huella_control: str,
) -> MovimientoBancarioCentral:
    """Adjunta evidencia sin crear otro pago y retira la revisión documental previa."""
    if not confirmacion:
        raise ValueError("Confirma la vinculación documental.")
    _validar_versiones(banco_repo, control_repo, huella_central, huella_control)
    movimientos = banco_repo.listar()
    actual = next((m for m in movimientos if m.identificador == identificador), None)
    if actual is None:
        raise ValueError("No existe el movimiento central.")
    archivo = preparar_adjunto(nombre, contenido)
    if archivo.referencia == actual.respaldo:
        raise ValueError("Ese voucher ya está vinculado a este movimiento.")
    for otro in movimientos:
        if otro.identificador != identificador and otro.respaldo == archivo.referencia:
            raise ValueError("El mismo voucher ya pertenece a otro movimiento central.")
    for factura in control_repo.listar():
        for pago in factura.movimientos_bancarios:
            if pago.documento_respaldo == archivo.referencia:
                raise ValueError("El voucher ya está vinculado a un pago histórico.")
    revision = _revision(
        "VINCULAR_EVIDENCIA",
        motivo,
        {
            "respaldo_anterior": actual.respaldo or "",
            "respaldo_nuevo": archivo.referencia,
            "archivo_original": nombre,
            "estado_anterior": actual.estado,
            "estado_nuevo": "BORRADOR",
        },
    )
    cambiado = actual.model_copy(update={
        "respaldo": archivo.referencia,
        "estado": "BORRADOR",
        "revisiones": [*actual.revisiones, revision],
    })
    _validar_versiones(banco_repo, control_repo, huella_central, huella_control)
    almacen.guardar(archivo)
    banco_repo.actualizar(cambiado, huella_esperada=huella_central)
    return cambiado


def documentar_movimiento_central(
    banco_repo: RepositorioMovimientosCentrales,
    control_repo: RepositorioControlFletes,
    almacen: AlmacenAdjuntos,
    identificador: str,
    *,
    motivo: str,
    confirmacion: bool,
    huella_central: str,
    huella_control: str,
) -> MovimientoBancarioCentral:
    """Revisa voucher y asignaciones; NO acredita saldos ni consulta el banco."""
    if not confirmacion:
        raise ValueError("Confirma que cotejaste referencia, importes y voucher.")
    _validar_versiones(banco_repo, control_repo, huella_central, huella_control)
    movimientos = banco_repo.listar()
    actual = next((m for m in movimientos if m.identificador == identificador), None)
    if actual is None:
        raise ValueError("No existe el movimiento central.")
    if actual.estado != "BORRADOR":
        raise ValueError("El movimiento ya cuenta con revisión documental.")
    if not actual.respaldo:
        raise ValueError("Primero adjunta el voucher bancario original.")
    almacen.abrir(actual.respaldo)
    _cotejar_distribucion(
        actual,
        control_repo.listar(),
        movimientos,
        [(a.expediente, str(a.importe)) for a in actual.aplicaciones],
    )
    revision = _revision(
        "DOCUMENTAR",
        motivo,
        {
            "referencia": actual.referencia,
            "respaldo": actual.respaldo,
            "total": str(actual.importe_total),
            "aplicado": str(actual.importe_total - actual.sin_asignar),
        },
    )
    cambiado = actual.model_copy(update={
        "estado": "DOCUMENTADO",
        "revisiones": [*actual.revisiones, revision],
    })
    _validar_versiones(banco_repo, control_repo, huella_central, huella_control)
    banco_repo.actualizar(cambiado, huella_esperada=huella_central)
    return cambiado


def reabrir_movimiento_central(
    banco_repo: RepositorioMovimientosCentrales,
    control_repo: RepositorioControlFletes,
    identificador: str,
    *,
    motivo: str,
    confirmacion: bool,
    huella_central: str,
    huella_control: str,
) -> MovimientoBancarioCentral:
    """Revierte una revisión documental conservando voucher y auditoría."""
    if not confirmacion:
        raise ValueError("Confirma la reapertura del movimiento.")
    _validar_versiones(banco_repo, control_repo, huella_central, huella_control)
    actual = banco_repo.obtener(identificador)
    if actual is None:
        raise ValueError("No existe el movimiento central.")
    if actual.estado != "DOCUMENTADO":
        raise ValueError("Solo pueden reabrirse movimientos documentados.")
    revision = _revision(
        "REABRIR",
        motivo,
        {"estado_anterior": actual.estado, "estado_nuevo": "BORRADOR"},
    )
    reabierto = actual.model_copy(update={
        "estado": "BORRADOR",
        "revisiones": [*actual.revisiones, revision],
    })
    _validar_versiones(banco_repo, control_repo, huella_central, huella_control)
    banco_repo.actualizar(reabierto, huella_esperada=huella_central)
    return reabierto


def _preparar_operacion_con_revision(
    operacion: OperacionFlete,
    pagos: list[MovimientoBancario],
    *,
    motivo: str,
    cambios: dict[str, str],
) -> OperacionFlete:
    revision = RevisionExpediente(
        fecha=datetime.now(UTC),
        motivo=motivo,
        cambios=cambios,
    )
    datos = operacion.model_dump(mode="python")
    datos["movimientos_bancarios"] = pagos
    datos["revisiones"] = [*operacion.revisiones, revision]
    datos["conciliacion_cerrada"] = False
    return OperacionFlete.model_validate(datos)


def aplicar_movimiento_central(
    banco_repo: RepositorioMovimientosCentrales,
    control_repo: RepositorioControlFletes,
    almacen: AlmacenAdjuntos,
    identificador: str,
    *,
    motivo: str,
    confirmacion: bool,
    huella_central: str,
    huella_control: str,
) -> MovimientoBancarioCentral:
    """Aplica un movimiento documentado a varios expedientes en un lote atómico.

    La escritura del control es idempotente: si el proceso se interrumpe después
    de guardar las aplicaciones pero antes de cambiar el estado central, la
    siguiente ejecución reconoce las aplicaciones existentes y finaliza el estado.
    """
    if not confirmacion:
        raise ValueError("Confirma la aplicación a los saldos del control financiero.")
    motivo = motivo.strip()
    if len(motivo) < 10:
        raise ValueError("El motivo de aplicación requiere al menos diez caracteres.")
    _validar_versiones(banco_repo, control_repo, huella_central, huella_control)
    movimientos = banco_repo.listar()
    actual = next((m for m in movimientos if m.identificador == identificador), None)
    if actual is None:
        raise ValueError("No existe el movimiento central.")
    if actual.estado == "APLICADO":
        raise ValueError("Este movimiento ya está aplicado a los expedientes.")
    if actual.estado != "DOCUMENTADO":
        raise ValueError("Primero documenta el movimiento antes de aplicarlo.")
    if not actual.respaldo:
        raise ValueError("El movimiento no tiene voucher original vinculado.")
    almacen.abrir(actual.respaldo)

    operaciones = control_repo.listar()
    aplicaciones = _cotejar_distribucion(
        actual,
        operaciones,
        movimientos,
        [(item.expediente, str(item.importe)) for item in actual.aplicaciones],
    )
    referencias = _referencias(actual.referencia)
    for operacion in operaciones:
        for pago in operacion.movimientos_bancarios:
            if pago.movimiento_central_id == identificador:
                continue
            if (
                any(ref in _referencias(pago.referencia or "") for ref in referencias)
                or pago.documento_respaldo == actual.respaldo
            ):
                raise ValueError(
                    "La referencia o el voucher ya figura en un pago ajeno al "
                    "movimiento central. Revisa el posible duplicado antes de aplicar."
                )

    por_expediente = {item.expediente: item for item in aplicaciones}
    nuevas_operaciones: list[OperacionFlete] = []
    for operacion in operaciones:
        pagos = list(operacion.movimientos_bancarios)
        posiciones = [
            indice for indice, pago in enumerate(pagos)
            if pago.movimiento_central_id == identificador
        ]
        if len(posiciones) > 1:
            raise ValueError(
                f"El expediente {operacion.identificador} contiene aplicaciones "
                "duplicadas del mismo movimiento central."
            )
        cambios: dict[str, str] = {}
        aplicacion = por_expediente.get(operacion.identificador)
        if aplicacion is not None:
            valores = {
                "importe_aplicado": aplicacion.importe,
                "moneda": actual.moneda,
                "referencia": actual.referencia,
                "documento_respaldo": actual.respaldo,
                "fecha": actual.fecha_operacion,
                "verificada": True,
                "movimiento_central_id": identificador,
            }
            if posiciones:
                indice = posiciones[0]
                anterior = pagos[indice]
                for campo, nuevo_valor in valores.items():
                    viejo_valor = getattr(anterior, campo)
                    if viejo_valor != nuevo_valor:
                        cambios[f"movimientos_bancarios[{indice}].{campo}"] = (
                            f"{viejo_valor!s} → {nuevo_valor!s}"
                        )
                if cambios:
                    pagos[indice] = anterior.model_copy(update=valores)
            else:
                indice = len(pagos)
                pagos.append(MovimientoBancario(**valores))
                cambios[f"movimientos_bancarios[{indice}]"] = (
                    f"Aplicación central {identificador}: "
                    f"{actual.referencia} · {aplicacion.importe} {actual.moneda.value}"
                )
        elif posiciones:
            indice = posiciones[0]
            anterior = pagos[indice]
            if anterior.verificada:
                pagos[indice] = anterior.model_copy(update={"verificada": False})
                cambios[f"movimientos_bancarios[{indice}].verificada"] = (
                    "True → False (la factura ya no pertenece a la distribución actual)"
                )
        if cambios:
            cambios["movimiento_central_id"] = identificador
            nuevas_operaciones.append(_preparar_operacion_con_revision(
                operacion,
                pagos,
                motivo=f"Aplicación del movimiento central {identificador}: {motivo}",
                cambios=cambios,
            ))

    huella_control_final = huella_control
    if nuevas_operaciones:
        control_repo.actualizar_lote(
            nuevas_operaciones,
            huella_esperada=huella_control,
        )
        huella_control_final = control_repo.huella()

    if banco_repo.huella() != huella_central:
        raise ValueError(
            "El control financiero contiene la aplicación, pero cambió el registro "
            "central. Actualiza la vista y repite la operación para finalizar el estado."
        )
    if control_repo.huella() != huella_control_final:
        raise ValueError(
            "Los expedientes cambiaron después de guardar. Revisa el movimiento "
            "antes de volver a aplicar."
        )
    revision = _revision(
        "APLICAR",
        motivo,
        {
            "estado_anterior": "DOCUMENTADO",
            "estado_nuevo": "APLICADO",
            "referencia": actual.referencia,
            "respaldo": actual.respaldo,
            "aplicaciones": ", ".join(
                f"{item.expediente}:{item.importe}" for item in actual.aplicaciones
            ),
        },
    )
    aplicado = actual.model_copy(update={
        "estado": "APLICADO",
        "revisiones": [*actual.revisiones, revision],
    })
    banco_repo.actualizar(aplicado, huella_esperada=huella_central)
    return aplicado


def revertir_aplicacion_central(
    banco_repo: RepositorioMovimientosCentrales,
    control_repo: RepositorioControlFletes,
    identificador: str,
    *,
    motivo: str,
    confirmacion: bool,
    huella_central: str,
    huella_control: str,
) -> MovimientoBancarioCentral:
    """Retira el efecto de conciliación; no anula ni elimina la transferencia bancaria."""
    if not confirmacion:
        raise ValueError("Confirma que deseas revertir la aplicación en los expedientes.")
    motivo = motivo.strip()
    if len(motivo) < 10:
        raise ValueError("El motivo de reversión requiere al menos diez caracteres.")
    _validar_versiones(banco_repo, control_repo, huella_central, huella_control)
    movimientos = banco_repo.listar()
    actual = next((m for m in movimientos if m.identificador == identificador), None)
    if actual is None:
        raise ValueError("No existe el movimiento central.")
    if actual.estado == "REVERTIDO":
        raise ValueError("La aplicación de este movimiento ya fue revertida.")
    if actual.estado != "APLICADO":
        raise ValueError("Solo se puede revertir un movimiento aplicado.")

    operaciones = control_repo.listar()
    aplicaciones = {item.expediente: item for item in actual.aplicaciones}
    registros: dict[str, tuple[OperacionFlete, int, MovimientoBancario]] = {}
    for operacion in operaciones:
        indices = [
            indice for indice, pago in enumerate(operacion.movimientos_bancarios)
            if pago.movimiento_central_id == identificador
        ]
        if len(indices) > 1:
            raise ValueError(
                f"El expediente {operacion.identificador} tiene aplicaciones "
                "duplicadas de este movimiento."
            )
        if not indices:
            continue
        indice = indices[0]
        pago = operacion.movimientos_bancarios[indice]
        if operacion.identificador not in aplicaciones:
            if pago.verificada:
                raise ValueError(
                    "Hay una aplicación activa fuera de la distribución central actual."
                )
            continue
        aplicacion = aplicaciones[operacion.identificador]
        if (
            pago.importe_aplicado != aplicacion.importe
            or pago.moneda != actual.moneda
            or pago.referencia != actual.referencia
            or pago.documento_respaldo != actual.respaldo
        ):
            raise ValueError(
                f"La aplicación de {operacion.identificador} ya no coincide con "
                "el registro central. Requiere conciliación manual."
            )
        registros[operacion.identificador] = (operacion, indice, pago)

    if set(registros) != set(aplicaciones):
        raise ValueError(
            "Faltan aplicaciones en los expedientes; no se puede revertir de forma segura."
        )
    estados = [registro[2].verificada for registro in registros.values()]
    if any(estados) and not all(estados):
        raise ValueError(
            "Las aplicaciones tienen estados mixtos. Revisa manualmente antes de revertir."
        )

    nuevas_operaciones: list[OperacionFlete] = []
    if all(estados):
        for operacion, indice, pago in registros.values():
            pagos = list(operacion.movimientos_bancarios)
            pagos[indice] = pago.model_copy(update={"verificada": False})
            nuevas_operaciones.append(_preparar_operacion_con_revision(
                operacion,
                pagos,
                motivo=f"Reversión de aplicación central {identificador}: {motivo}",
                cambios={
                    f"movimientos_bancarios[{indice}].verificada": "True → False",
                    f"movimientos_bancarios[{indice}].movimiento_central_id": identificador,
                    "importe_revertido": str(pago.importe_aplicado),
                    "referencia": actual.referencia,
                },
            ))
    huella_control_final = huella_control
    if nuevas_operaciones:
        control_repo.actualizar_lote(
            nuevas_operaciones,
            huella_esperada=huella_control,
        )
        huella_control_final = control_repo.huella()

    if banco_repo.huella() != huella_central:
        raise ValueError(
            "La reversión está guardada en los expedientes, pero cambió el registro "
            "central. Actualiza la vista y repite la operación para finalizar el estado."
        )
    if control_repo.huella() != huella_control_final:
        raise ValueError(
            "Los expedientes cambiaron después de la reversión; revisa el registro central."
        )
    revision = _revision(
        "REVERTIR_APLICACION",
        motivo,
        {
            "estado_anterior": "APLICADO",
            "estado_nuevo": "REVERTIDO",
            "referencia": actual.referencia,
            "aplicaciones": ", ".join(
                f"{item.expediente}:{item.importe}" for item in actual.aplicaciones
            ),
            "nota": "Se retiró el efecto en conciliación; el movimiento bancario permanece.",
        },
    )
    revertido = actual.model_copy(update={
        "estado": "REVERTIDO",
        "revisiones": [*actual.revisiones, revision],
    })
    banco_repo.actualizar(revertido, huella_esperada=huella_central)
    return revertido

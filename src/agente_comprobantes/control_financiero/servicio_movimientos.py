"""Servicio de aplicaciones bancarias, todavía sin impacto en conciliación."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from agente_comprobantes.control_financiero.archivos import AlmacenAdjuntos, preparar_adjunto
from agente_comprobantes.control_financiero.auditoria_importacion import (
    _referencias,
)
from agente_comprobantes.control_financiero.modelos import OperacionFlete
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
) -> MovimientoBancarioCentral:
    """Comprobar saldos declarados y referencias sin tocar registros existentes."""
    borrador = MovimientoBancarioCentral(
        identificador="MB-" + uuid4().hex[:12].upper(),
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
            if objetivo in _referencias(pago.referencia or ""):
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
        {"estado_anterior": "DOCUMENTADO", "estado_nuevo": "BORRADOR"},
    )
    reabierto = actual.model_copy(update={
        "estado": "BORRADOR",
        "revisiones": [*actual.revisiones, revision],
    })
    _validar_versiones(banco_repo, control_repo, huella_central, huella_control)
    banco_repo.actualizar(reabierto, huella_esperada=huella_central)
    return reabierto

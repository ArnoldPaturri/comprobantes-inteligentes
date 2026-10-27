"""Editor localizado de incidencias de expedientes existentes.

Solo permite corregir MOVIMIENTOS DECLARADOS sin acreditación documental:
desglosar una referencia compuesta o reclasificar EFECTIVO como pendiente.
"""

from __future__ import annotations

from decimal import Decimal

import streamlit as st

from agente_comprobantes.configuracion import Configuracion
from agente_comprobantes.control_financiero.auditoria_importacion import _referencias
from agente_comprobantes.control_financiero.editor_incidencias import (
    guardar_desglose,
    guardar_reclasificacion_efectivo,
)
from agente_comprobantes.control_financiero.modelos import OperacionFlete
from agente_comprobantes.control_financiero.repositorio_json import (
    RepositorioControlFletes,
)
from agente_comprobantes.control_financiero.tipos_referencia import (
    indicador_efectivo,
)


def _repositorio() -> RepositorioControlFletes:
    return RepositorioControlFletes(
        Configuracion().ruta_archivo_excel().with_name("control_fletes.json")
    )


def _guardado(identificador: str) -> None:
    st.session_state["_mensaje_revision"] = (
        f"Corrección declarada registrada en {identificador}. "
        "Los pagos siguen sin acreditación documental."
    )
    st.rerun()


def _desglose_formulario(
    op: OperacionFlete, indice: int, referencia: str,
) -> None:
    partes = _referencias(referencia)
    if len(partes) < 2 or len(partes) > 10:
        st.warning("La referencia no admite un desglose de 2 a 10 movimientos.")
        return
    st.caption(
        "Indica cuánto corresponde a cada referencia según los vouchers. "
        "La suma debe coincidir exactamente con el importe declarado. "
        "El respaldo antiguo NO se asignará automáticamente a los pagos nuevos."
    )
    with st.form(f"desglose_{op.identificador}_{indice}"):
        importes = [
            st.text_input(
                f"Importe de {parte} ({op.moneda.value})",
                placeholder="0.00",
                key=f"monto_desglose_{op.identificador}_{indice}_{i}",
            )
            for i, parte in enumerate(partes)
        ]
        motivo = st.text_area(
            "Sustento de la distribución",
            placeholder="Documentos revisados y criterio para cada monto declarado.",
        )
        confirmado = st.checkbox(
            "Contrasté las referencias y los importes con los comprobantes "
            "correspondientes. El desglose quedará sin acreditar."
        )
        enviado = st.form_submit_button("Guardar desglose declarado")
    if not enviado:
        return
    try:
        guardar_desglose(
            _repositorio(), op.identificador,
            indice=indice,
            asignaciones=list(zip(partes, importes, strict=True)),
            motivo=motivo,
            confirmacion=confirmado,
            version_esperada=len(op.revisiones),
        )
    except (ValueError, OSError) as error:
        st.error(str(error))
        return
    _guardado(op.identificador)


def _efectivo_formulario(op: OperacionFlete, indice: int) -> None:
    st.warning(
        "No podemos afirmar que este pago haya sido bancarizado. "
        "La reclasificación conserva el importe como declaración por aclarar, "
        "fuera de los movimientos bancarios y sin acreditación."
    )
    with st.form(f"efectivo_{op.identificador}_{indice}"):
        motivo = st.text_area(
            "Motivo de reclasificación",
            placeholder="Se revisó la etiqueta de efectivo y falta validar el sustento.",
        )
        confirmado = st.checkbox(
            "Confirmo que el dato debe quedar por aclarar y no como "
            "operación bancaria. No estoy acreditando el pago."
        )
        enviado = st.form_submit_button("Reclasificar como pendiente")
    if not enviado:
        return
    try:
        guardar_reclasificacion_efectivo(
            _repositorio(), op.identificador,
            indice=indice,
            motivo=motivo,
            confirmacion=confirmado,
            version_esperada=len(op.revisiones),
        )
    except (ValueError, OSError) as error:
        st.error(str(error))
        return
    _guardado(op.identificador)


def mostrar_editor_incidencias(
    op: OperacionFlete,
    *,
    tipo: str,
) -> None:
    st.markdown(f"**Expediente: {op.numero_factura}**")
    st.caption(
        f"{op.identificador} · {op.proveedor or 'Sin proveedor'} "
        f"· {op.moneda.value}"
    )
    st.info(
        "La edición no verifica bancos ni SUNAT. "
        "Se conserva el valor del Excel y un historial de la corrección."
    )
    opciones = []
    for indice, pago in enumerate(op.movimientos_bancarios):
        referencia = pago.referencia or ""
        if tipo == "REFERENCIAS MÚLTIPLES" and len(_referencias(referencia)) > 1:
            opciones.append(indice)
        elif tipo in {"EFECTIVO SIN OPERACIÓN", "EFECTIVO POR CONFIRMAR"}:
            if indicador_efectivo(referencia):
                opciones.append(indice)

    if not opciones:
        st.warning(
            "No hay un movimiento bancario editable para esta incidencia. "
            "Podría haber sido corregida o quedar solo en el dato original."
        )
        return

    indice = st.selectbox(
        "Movimiento declarado por revisar",
        opciones,
        format_func=lambda i: (
            f"{op.movimientos_bancarios[i].referencia} · "
            f"{op.movimientos_bancarios[i].importe_aplicado:,.2f} {op.moneda.value}"
        ),
        key=f"mov_a_corregir_{op.identificador}_{tipo}",
    )
    pago = op.movimientos_bancarios[indice]
    if pago.verificada:
        st.error(
            "Este movimiento tiene acreditación documental. Primero debes "
            "retirarla desde la pestaña Revisar pagos del expediente."
        )
        return
    if op.conciliacion_cerrada:
        st.error("La conciliación está cerrada; primero debe reabrirse.")
        return
    if tipo == "REFERENCIAS MÚLTIPLES":
        _desglose_formulario(op, indice, pago.referencia or "")
    elif tipo in {"EFECTIVO SIN OPERACIÓN", "EFECTIVO POR CONFIRMAR"}:
        _efectivo_formulario(op, indice)


def mostrar_declaraciones_pendientes(op: OperacionFlete) -> None:
    if not op.declaraciones_por_aclarar:
        return
    total = sum(
        (p.importe_declarado for p in op.declaraciones_por_aclarar),
        Decimal("0"),
    )
    st.warning(
        f"{len(op.declaraciones_por_aclarar)} declaración(es) por aclarar "
        f"· total declarado {total:,.2f} {op.moneda.value}. "
        "No se incluyen como operaciones bancarias acreditadas."
    )
    st.dataframe(
        [
            {
                "Referencia original": item.referencia_original,
                "Importe declarado": str(item.importe_declarado),
                "Moneda": item.moneda.value,
                "Respaldo heredado": item.respaldo_original or "Sin respaldo",
                "Situación": "Requiere sustento",
            }
            for item in op.declaraciones_por_aclarar
        ],
        hide_index=True,
        use_container_width=True,
    )

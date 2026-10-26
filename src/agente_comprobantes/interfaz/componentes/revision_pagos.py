"""Formulario de revisión manual de pagos asociados al expediente."""

from __future__ import annotations

import streamlit as st

from agente_comprobantes.configuracion import Configuracion
from agente_comprobantes.control_financiero.modelos import OperacionFlete
from agente_comprobantes.control_financiero.repositorio_json import (
    RepositorioControlFletes,
)
from agente_comprobantes.control_financiero.revision_pagos import (
    guardar_revision_pago,
)
from agente_comprobantes.control_financiero.presentacion import formatear_importe


def mostrar_revision_pagos(operacion: OperacionFlete) -> None:
    st.caption(
        "Revisión de evidencia documental. Esta acción NO confirma transacciones "
        "en el banco, no modifica pagos en Excel y no cierra conciliaciones."
    )
    if not operacion.movimientos_bancarios:
        st.info("Esta factura todavía no tiene comprobantes de pago asociados.")
        return

    movimientos = operacion.movimientos_bancarios
    indice = st.selectbox(
        "Comprobante de pago",
        list(range(len(movimientos))),
        format_func=lambda i: (
            f"#{i + 1} · {movimientos[i].referencia or 'Sin referencia'} · "
            f"{formatear_importe(movimientos[i].importe_aplicado, movimientos[i].moneda)}"
        ),
        key=f"pago_seleccion_{operacion.identificador}",
    )
    seleccionado = movimientos[indice]

    datos = st.columns(3)
    datos[0].metric(
        "Importe del comprobante",
        formatear_importe(seleccionado.importe_aplicado, seleccionado.moneda),
    )
    datos[1].write("**Referencia**")
    datos[1].write(seleccionado.referencia or "No identificada")
    datos[2].write("**Archivo de origen**")
    datos[2].write(seleccionado.documento_respaldo or "No disponible")
    st.info(
        "Para revisarlo, consulta el comprobante original fuera de esta pantalla. "
        "Un nombre de archivo o el resultado del OCR no acreditan por sí solos el pago."
    )
    accion = (
        "Retirar validación documental"
        if seleccionado.verificada else "Validar evidencia documental"
    )
    with st.form(f"revision_pago_{operacion.identificador}_{indice}"):
        motivo = st.text_area(
            "Sustento de esta decisión",
            placeholder="Indica el documento examinado y el criterio de revisión.",
        )
        confirmado = st.checkbox(
            "He revisado el comprobante original y contrastado referencia, "
            "importe y moneda. Esta validación es documental, no bancaria."
        )
        enviado = st.form_submit_button(accion, type="primary")

    if not enviado:
        return

    try:
        actualizado = guardar_revision_pago(
            RepositorioControlFletes(
                Configuracion().ruta_archivo_excel().with_name("control_fletes.json")
            ),
            operacion.identificador,
            indice=indice,
            acreditar=not seleccionado.verificada,
            motivo=motivo,
            confirmacion=confirmado,
            version_esperada=len(operacion.revisiones),
        )
    except (ValueError, OSError) as error:
        st.error(str(error))
        return

    st.session_state["_mensaje_revision"] = (
        f"Revisión documental registrada en {actualizado.identificador}. "
        "El Excel de origen no fue modificado."
    )
    st.rerun()

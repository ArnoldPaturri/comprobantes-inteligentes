"""Formulario de revisión manual de pagos asociados al expediente."""

from __future__ import annotations

import streamlit as st

from agente_comprobantes.configuracion import Configuracion
from agente_comprobantes.control_financiero.adjuntos import guardar_adjunto_existente
from agente_comprobantes.control_financiero.archivos import almacen_para_excel
from agente_comprobantes.control_financiero.modelos import OperacionFlete
from agente_comprobantes.control_financiero.presentacion import formatear_importe
from agente_comprobantes.control_financiero.repositorio_json import (
    RepositorioControlFletes,
)
from agente_comprobantes.control_financiero.revision_pagos import (
    guardar_revision_pago,
)
from agente_comprobantes.control_financiero.repositorio_movimientos import (
    RepositorioMovimientosCentrales,
)
from agente_comprobantes.control_financiero.validacion_bancarizaciones import (
    validar_cotejo_pago,
)
from agente_comprobantes.interfaz.componentes.visor_adjuntos import mostrar_respaldo


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
    mostrar_respaldo(
        seleccionado.documento_respaldo,
        clave=f"pago_{operacion.identificador}_{indice}",
    )
    if not (seleccionado.documento_respaldo or "").startswith("adjunto:"):
        st.warning(
            "Primero adjunta el comprobante real. El OCR y el nombre del archivo "
            "no constituyen una validación documental."
        )
        _cargar_comprobante_pago(operacion, indice)
        return

    _cargar_comprobante_pago(operacion, indice)
    if not seleccionado.verificada:
        destino = RepositorioControlFletes(
            Configuracion().ruta_archivo_excel().with_name("control_fletes.json")
        )
        try:
            validar_cotejo_pago(
                operacion,
                indice,
                otros_expedientes=destino.listar(),
                movimientos_centrales=RepositorioMovimientosCentrales(
                    Configuracion().ruta_archivo_excel().with_name(
                        "movimientos_bancarios_centrales.json"
                    )
                ).listar(),
            )
        except (ValueError, OSError) as error:
            st.warning(
                f"Este comprobante todavía no se puede acreditar: {error}"
            )
            st.caption(
                "Si el número de operación contiene varias referencias, "
                "utiliza el editor de incidencias. Si figura en otras "
                "facturas, revisa primero su distribución documentada."
            )
            return
        st.success(
            "Comprobante apto para una revisión documental manual. "
            "Aún no se ha acreditado ni confirmado en el banco."
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


def _cargar_comprobante_pago(operacion: OperacionFlete, indice: int) -> None:
    with st.expander("Adjuntar o reemplazar comprobante original"):
        with st.form(f"adjuntar_pago_{operacion.identificador}_{indice}"):
            archivo = st.file_uploader(
                "Selecciona PDF, PNG o JPG",
                type=["pdf", "png", "jpg", "jpeg"],
                max_upload_size=8,
                key=f"archivo_pago_{operacion.identificador}_{indice}",
            )
            motivo = st.text_area(
                "Sustento de la carga",
                placeholder="Documento original revisado y vinculado con esta factura.",
            )
            confirmado = st.checkbox(
                "Confirmo que el respaldo corresponde al pago seleccionado; "
                "si se reemplaza uno anterior, se retirará su validación."
            )
            enviado = st.form_submit_button("Guardar comprobante")
        if not enviado:
            return
        if archivo is None:
            st.error("Adjunta un archivo para guardar.")
            return
        try:
            guardar_adjunto_existente(
                RepositorioControlFletes(
                    Configuracion().ruta_archivo_excel().with_name("control_fletes.json")
                ),
                almacen_para_excel(Configuracion().ruta_archivo_excel()),
                operacion.identificador,
                destino="pago",
                indice=indice,
                nombre=archivo.name,
                contenido=archivo.getvalue(),
                motivo=motivo,
                confirmacion=confirmado,
                version_esperada=len(operacion.revisiones),
            )
        except (ValueError, OSError) as exc:
            st.error(str(exc))
            return
        st.session_state["_mensaje_revision"] = (
            "Archivo real vinculado al pago. Requiere una nueva revisión documental."
        )
        st.rerun()

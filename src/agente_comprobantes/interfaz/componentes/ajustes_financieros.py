"""Alta y revisión de detracciones y notas de crédito con adjuntos reales."""

from __future__ import annotations

import streamlit as st

from agente_comprobantes.configuracion import Configuracion
from agente_comprobantes.control_financiero.adjuntos import (
    guardar_adjunto_existente,
    guardar_ajuste_con_archivo,
)
from agente_comprobantes.control_financiero.archivos import almacen_para_excel
from agente_comprobantes.control_financiero.modelos import OperacionFlete
from agente_comprobantes.control_financiero.presentacion import formatear_importe
from agente_comprobantes.control_financiero.registro_ajustes import (
    guardar_revision_evidencia,
)
from agente_comprobantes.control_financiero.repositorio_json import (
    RepositorioControlFletes,
)
from agente_comprobantes.interfaz.componentes.visor_adjuntos import mostrar_respaldo

TIPOS = {"Depósito de detracción": "detraccion", "Nota de crédito": "nota_credito"}


def _repositorio() -> RepositorioControlFletes:
    ruta = Configuracion().ruta_archivo_excel().with_name("control_fletes.json")
    return RepositorioControlFletes(ruta)


def _almacen():
    return almacen_para_excel(Configuracion().ruta_archivo_excel())


def _resultado_guardado(identificador: str) -> None:
    st.session_state["_mensaje_revision"] = (
        f"Cambio guardado en {identificador}. El Excel de origen no se modificó."
    )
    st.rerun()


def _formulario_registro(operacion: OperacionFlete) -> None:
    st.markdown("**Registrar evidencia nueva**")
    st.caption(
        "Adjunta un PDF o una imagen JPG/PNG de hasta 8 MB. Se conservará una "
        "copia local verificada por hash; el registro inicial no quedará acreditado."
    )
    with st.form(f"registrar_ajuste_{operacion.identificador}"):
        etiqueta = st.selectbox("Tipo de documento", list(TIPOS))
        numero = st.text_input(
            "Número de nota de crédito (solo para notas)",
            placeholder="FC01-0005",
        )
        referencia = st.text_input(
            "Referencia u operación",
            placeholder="Número de depósito o referencia de nota de crédito",
        )
        monto = st.text_input(
            f"Importe ({operacion.moneda.value})", placeholder="0.00"
        )
        documento = st.file_uploader(
            "Adjuntar documento original",
            type=["pdf", "png", "jpg", "jpeg"],
            max_upload_size=8,
            key=f"nuevo_ajuste_{operacion.identificador}",
        )
        motivo = st.text_area(
            "Sustento del registro",
            placeholder="Indica la relación entre documento, importe y factura.",
        )
        confirmado = st.checkbox(
            "He identificado el documento y confirmo que la revisión de "
            "acreditación se realizará por separado."
        )
        enviado = st.form_submit_button("Registrar sin acreditar", type="primary")
    if not enviado:
        return
    if documento is None:
        st.error("Adjunta el comprobante para continuar.")
        return

    try:
        guardar_ajuste_con_archivo(
            _repositorio(), _almacen(), operacion.identificador,
            tipo=TIPOS[etiqueta], referencia=referencia, monto=monto,
            numero=numero, nombre=documento.name, contenido=documento.getvalue(),
            motivo=motivo, confirmacion=confirmado,
            version_esperada=len(operacion.revisiones),
        )
    except (ValueError, OSError) as exc:
        st.error(str(exc))
        return
    _resultado_guardado(operacion.identificador)


def _formulario_acreditacion(operacion: OperacionFlete) -> None:
    items = [
        ("detraccion", i, item)
        for i, item in enumerate(operacion.depositos_detraccion)
    ] + [
        ("nota_credito", i, item)
        for i, item in enumerate(operacion.notas_credito)
    ]
    st.markdown("**Revisar documentos registrados**")
    if not items:
        st.info("No hay detracciones ni notas de crédito asociadas.")
        return

    def etiqueta_opcion(posicion: int) -> str:
        tipo, _, item = items[posicion]
        nombre = "Detracción" if tipo == "detraccion" else "Nota de crédito"
        return (
            f"{nombre} · {item.referencia or 'Sin referencia'} · "
            f"{formatear_importe(item.importe, item.moneda)}"
        )

    seleccionado = st.selectbox(
        "Documento", list(range(len(items))), format_func=etiqueta_opcion,
        key=f"ajuste_seleccionado_{operacion.identificador}",
    )
    tipo, indice, item = items[seleccionado]
    st.caption(
        "Estado: "
        + ("Revisión documental acreditada" if item.verificada else "Sin acreditar")
    )
    mostrar_respaldo(
        item.documento_respaldo,
        clave=f"ajuste_{operacion.identificador}_{tipo}_{indice}",
    )

    if not (item.documento_respaldo or "").startswith("adjunto:"):
        _adjuntar_a_registro(operacion, tipo, indice)
        return

    accion = (
        "Retirar acreditación documental"
        if item.verificada else "Acreditar revisión documental"
    )
    with st.form(f"acreditar_ajuste_{operacion.identificador}_{tipo}_{indice}"):
        motivo = st.text_area(
            "Motivo de esta decisión",
            placeholder="Indica qué comprobaste en el documento original.",
        )
        confirmado = st.checkbox(
            "He contrastado el archivo adjunto con la factura y con "
            "la referencia, importe y moneda de la evidencia."
        )
        enviado = st.form_submit_button(accion, type="primary")
    if enviado:
        try:
            guardar_revision_evidencia(
                _repositorio(), operacion.identificador,
                tipo=tipo, indice=indice, acreditar=not item.verificada,
                motivo=motivo, confirmacion=confirmado,
                version_esperada=len(operacion.revisiones),
            )
        except (ValueError, OSError) as exc:
            st.error(str(exc))
        else:
            _resultado_guardado(operacion.identificador)
    _adjuntar_a_registro(operacion, tipo, indice)


def _adjuntar_a_registro(operacion: OperacionFlete, tipo: str, indice: int) -> None:
    with st.expander("Adjuntar o reemplazar respaldo original"):
        with st.form(f"reemplazar_{operacion.identificador}_{tipo}_{indice}"):
            archivo = st.file_uploader(
                "PDF o imagen",
                type=["pdf", "jpg", "jpeg", "png"],
                max_upload_size=8,
                key=f"archivo_existente_{operacion.identificador}_{tipo}_{indice}",
            )
            motivo = st.text_area("Motivo del reemplazo o incorporación")
            confirmacion = st.checkbox(
                "Confirmo que el archivo corresponde a esta evidencia. "
                "Se retirará cualquier acreditación documental anterior."
            )
            enviado = st.form_submit_button("Guardar archivo")
        if enviado:
            if archivo is None:
                st.error("Selecciona un documento.")
                return
            try:
                guardar_adjunto_existente(
                    _repositorio(), _almacen(), operacion.identificador,
                    destino=tipo, indice=indice, nombre=archivo.name,
                    contenido=archivo.getvalue(), motivo=motivo,
                    confirmacion=confirmacion,
                    version_esperada=len(operacion.revisiones),
                )
            except (OSError, ValueError) as exc:
                st.error(str(exc))
            else:
                _resultado_guardado(operacion.identificador)


def mostrar_ajustes_financieros(operacion: OperacionFlete) -> None:
    st.caption(
        "Detracciones y notas de crédito con respaldo real, revisión humana "
        "y registro independiente del Excel."
    )
    if operacion.es_flete is not True or operacion.detraccion_aplica is not True:
        st.warning(
            "Para registrar detracciones confirma primero la naturaleza del "
            "flete y la aplicabilidad. Las notas de crédito se manejan aparte."
        )
    registro, revisar = st.tabs(["Registrar documento", "Revisar documentos"])
    with registro:
        _formulario_registro(operacion)
    with revisar:
        _formulario_acreditacion(operacion)

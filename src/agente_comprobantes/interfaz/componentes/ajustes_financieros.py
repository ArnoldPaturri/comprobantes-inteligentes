"""Alta y revisión manual de detracciones y notas de crédito en Streamlit."""

from __future__ import annotations

import streamlit as st

from agente_comprobantes.configuracion import Configuracion
from agente_comprobantes.control_financiero.modelos import OperacionFlete
from agente_comprobantes.control_financiero.presentacion import formatear_importe
from agente_comprobantes.control_financiero.registro_ajustes import (
    guardar_registro_evidencia,
    guardar_revision_evidencia,
)
from agente_comprobantes.control_financiero.repositorio_json import (
    RepositorioControlFletes,
)

TIPOS = {"Depósito de detracción": "detraccion", "Nota de crédito": "nota_credito"}


def _repositorio() -> RepositorioControlFletes:
    ruta = Configuracion().ruta_archivo_excel().with_name("control_fletes.json")
    return RepositorioControlFletes(ruta)


def _resultado_guardado(identificador: str) -> None:
    st.session_state["_mensaje_revision"] = (
        f"Cambio registrado en {identificador}. El Excel original sigue intacto."
    )
    st.rerun()


def _formulario_registro(operacion: OperacionFlete) -> None:
    st.markdown("**Registrar evidencia nueva**")
    st.caption(
        "Se registra sin acreditación. Indicar un nombre de archivo no lo adjunta "
        "ni demuestra su existencia; conserva el documento original por separado."
    )
    with st.form(f"registrar_ajuste_{operacion.identificador}"):
        etiqueta = st.selectbox("Tipo de documento", list(TIPOS))
        numero = st.text_input(
            "Número de nota de crédito (solo para notas)",
            placeholder="FC01-0005",
            help="Obligatorio únicamente cuando registras una nota de crédito.",
        )
        referencia = st.text_input(
            "Referencia documental u operación",
            placeholder="Número de depósito o referencia de nota de crédito",
        )
        monto = st.text_input(
            f"Importe ({operacion.moneda.value})",
            placeholder="0.00",
            help="Usar punto decimal, sin separadores de miles.",
        )
        respaldo = st.text_input(
            "Nombre del comprobante original",
            placeholder="constancia_001.pdf",
        )
        motivo = st.text_area(
            "Motivo del registro",
            placeholder="Se revisó la documentación que identifica este importe.",
        )
        confirmado = st.checkbox(
            "Confirmo que he identificado el documento correspondiente y "
            "que estos datos requieren una revisión de acreditación aparte."
        )
        enviado = st.form_submit_button("Registrar sin acreditar", type="primary")
    if not enviado:
        return
    try:
        guardar_registro_evidencia(
            _repositorio(),
            operacion.identificador,
            tipo=TIPOS[etiqueta],
            referencia=referencia,
            respaldo=respaldo,
            monto=monto,
            numero=numero,
            motivo=motivo,
            confirmacion=confirmado,
            version_esperada=len(operacion.revisiones),
        )
    except (ValueError, OSError) as exc:
        st.error(str(exc))
        return
    _resultado_guardado(operacion.identificador)


def _formulario_acreditacion(operacion: OperacionFlete) -> None:
    items = [
        ("detraccion", index, item)
        for index, item in enumerate(operacion.depositos_detraccion)
    ] + [
        ("nota_credito", index, item)
        for index, item in enumerate(operacion.notas_credito)
    ]
    st.markdown("**Revisar evidencias registradas**")
    if not items:
        st.info("Este expediente aún no tiene detracciones ni notas de crédito.")
        return

    def nombre(indice: int) -> str:
        tipo, _, item = items[indice]
        etiqueta = "Detracción" if tipo == "detraccion" else "Nota de crédito"
        return (
            f"{etiqueta} · {item.referencia or 'Sin referencia'} · "
            f"{formatear_importe(item.importe, item.moneda)}"
        )

    seleccionado = st.selectbox(
        "Documento",
        list(range(len(items))),
        format_func=nombre,
        key=f"documento_ajuste_{operacion.identificador}",
    )
    tipo, indice, item = items[seleccionado]
    st.caption(f"Respaldo declarado: {item.documento_respaldo or 'No registrado'}")
    st.info(
        "Esta revisión es documental, declarada por el operador. No comprueba "
        "depósitos en SUNAT ni valida automáticamente la nota de crédito."
    )
    accion = (
        "Retirar acreditación documental"
        if item.verificada else "Acreditar revisión documental"
    )
    with st.form(f"acreditar_ajuste_{operacion.identificador}_{tipo}_{indice}"):
        motivo = st.text_area(
            "Sustento de acreditación o reversión",
            placeholder="Detalle lo que comprobaste en el documento original.",
        )
        confirmado = st.checkbox(
            "Confirmo que revisé manualmente el documento, la referencia, "
            "el importe, la moneda y su vinculación con esta factura."
        )
        enviado = st.form_submit_button(accion, type="primary")
    if not enviado:
        return
    try:
        guardar_revision_evidencia(
            _repositorio(),
            operacion.identificador,
            tipo=tipo,
            indice=indice,
            acreditar=not item.verificada,
            motivo=motivo,
            confirmacion=confirmado,
            version_esperada=len(operacion.revisiones),
        )
    except (ValueError, OSError) as exc:
        st.error(str(exc))
        return
    _resultado_guardado(operacion.identificador)


def mostrar_ajustes_financieros(operacion: OperacionFlete) -> None:
    st.caption(
        "Control de detracciones y notas de crédito: "
        "registro separado, revisión humana e historial local."
    )
    if operacion.es_flete is not True or operacion.detraccion_aplica is not True:
        st.warning(
            "Para registrar depósitos de detracción, primero confirma que "
            "el expediente es un flete sujeto a detracción. "
            "Las notas de crédito pueden registrarse por separado."
        )
    registro, acreditacion = st.tabs(["Registrar documento", "Revisar documentos"])
    with registro:
        _formulario_registro(operacion)
    with acreditacion:
        _formulario_acreditacion(operacion)

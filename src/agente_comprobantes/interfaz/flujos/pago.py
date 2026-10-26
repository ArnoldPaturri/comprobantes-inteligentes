from __future__ import annotations

from pathlib import Path

import streamlit as st

from agente_comprobantes.dominio import ExtraccionDocumento
from agente_comprobantes.excepciones import ErrorAgenteComprobantes
from agente_comprobantes.interfaz.componentes.editor_extraccion import mostrar_editor_extraccion
from agente_comprobantes.interfaz.contexto import ContextoAplicacion

_PREVIEW_KEY = "_payment_preview"
_PATHS_KEY = "_payment_paths"
_QUOTATION_KEY = "_payment_quotation"
_INVOICE_KEY = "_payment_invoice"
_MODE_KEY = "_payment_mode"
_RESULT_KEY = "_payment_result"

_MODE_WITH_INVOICE = "Aplicar a una factura existente"
_MODE_WITHOUT_INVOICE = "Registrar antes de recibir la factura"


def limpiar_previsualizacion() -> None:
    st.session_state.pop(_PREVIEW_KEY, None)
    st.session_state.pop(_PATHS_KEY, None)
    st.session_state.pop(_QUOTATION_KEY, None)
    st.session_state.pop(_INVOICE_KEY, None)
    st.session_state.pop(_MODE_KEY, None)


def mostrar_revision_pago(
    previsualizacion: ExtraccionDocumento,
    contexto: ContextoAplicacion,
) -> None:
    image_paths = st.session_state.get(
        _PATHS_KEY,
        [],
    )
    confirmed_quotation = st.session_state.get(
        _QUOTATION_KEY,
        "",
    )
    confirmed_invoice = st.session_state.get(
        _INVOICE_KEY
    )
    confirmed_mode = st.session_state.get(
        _MODE_KEY,
        "",
    )

    st.info(
        f"Cotización: {confirmed_quotation}\n\n"
        f"Flujo: {confirmed_mode}"
    )

    if confirmed_invoice:
        st.info(
            f"Factura seleccionada: {confirmed_invoice}"
        )
    else:
        st.warning(
            "Este pago quedará pendiente hasta que se "
            "registre su factura."
        )

    with st.expander("Ver imágenes analizadas"):
        for image_path in image_paths:
            st.image(
                image_path,
                caption=Path(image_path).name,
                width=400,
            )

    if st.button(
        "Descartar análisis y comenzar nuevamente",
        use_container_width=True,
    ):
        limpiar_previsualizacion()
        st.rerun()

    confirmed_extraction = mostrar_editor_extraccion(
        previsualizacion,
        key_prefix="payment",
    )

    if confirmed_extraction is None:
        return

    try:
        with st.spinner("Registrando el pago..."):
            result = contexto.agent.registrar_pago(
                confirmed_quotation,
                image_paths,
                invoice_id=confirmed_invoice,
                confirmed_extraction=confirmed_extraction,
            )
    except (
        ErrorAgenteComprobantes,
        OSError,
        ValueError,
    ) as exc:
        st.error(
            f"No se pudo registrar el pago: {exc}"
        )
        return

    st.session_state[_RESULT_KEY] = (
        result.model_dump(mode="json")
    )
    limpiar_previsualizacion()
    st.rerun()

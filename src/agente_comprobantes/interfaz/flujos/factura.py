from __future__ import annotations

from pathlib import Path

import streamlit as st

from agente_comprobantes.dominio import ExtraccionDocumento
from agente_comprobantes.excepciones import ErrorAgenteComprobantes
from agente_comprobantes.interfaz.componentes.editor_extraccion import mostrar_editor_extraccion
from agente_comprobantes.interfaz.contexto import ContextoAplicacion

_PREVIEW_KEY = "_invoice_preview"
_PATHS_KEY = "_invoice_paths"
_QUOTATION_KEY = "_invoice_quotation_code"
_RESULT_KEY = "_invoice_result"
_ELAPSED_KEY = "_invoice_elapsed_seconds"


def limpiar_previsualizacion() -> None:
    st.session_state.pop(_PREVIEW_KEY, None)
    st.session_state.pop(_PATHS_KEY, None)
    st.session_state.pop(_QUOTATION_KEY, None)
    st.session_state.pop(_ELAPSED_KEY, None)


def mostrar_revision_factura(
    previsualizacion: ExtraccionDocumento,
    contexto: ContextoAplicacion,
) -> None:
    image_paths = st.session_state.get(
        _PATHS_KEY,
        [],
    )
    confirmed_code = st.session_state.get(
        _QUOTATION_KEY,
        "",
    )
    elapsed = st.session_state.get(_ELAPSED_KEY)

    st.info(
        f"Revisando factura para: {confirmed_code}"
    )

    if isinstance(elapsed, (int, float)):
        st.caption(
            "Extracción completada en "
            f"{elapsed:.1f} segundos."
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
        key_prefix="invoice",
    )

    if confirmed_extraction is None:
        return

    try:
        with st.spinner(
            "Registrando y comparando la factura..."
        ):
            result = contexto.agent.registrar_factura(
                confirmed_code,
                image_paths,
                confirmed_extraction=confirmed_extraction,
            )
    except (
        ErrorAgenteComprobantes,
        OSError,
        ValueError,
    ) as exc:
        st.error(
            f"No se pudo registrar la factura: {exc}"
        )
        return

    st.session_state[_RESULT_KEY] = (
        result.model_dump(mode="json")
    )
    limpiar_previsualizacion()
    st.rerun()

from __future__ import annotations

from pathlib import Path

import streamlit as st

from agente_comprobantes.dominio import (
    ExtraccionDocumento,
    TipoDocumento,
)
from agente_comprobantes.excepciones import ErrorAgenteComprobantes
from agente_comprobantes.interfaz.cargas import guardar_archivos_cargados
from agente_comprobantes.interfaz.componentes.editor_extraccion import (
    mostrar_editor_extraccion,
)
from agente_comprobantes.interfaz.contexto import obtener_contexto_aplicacion

_PREVIEW_KEY = "_quotation_preview"
_PATHS_KEY = "_quotation_paths"
_CODE_KEY = "_quotation_confirmed_code"
_RESULT_KEY = "_quotation_result"


def _limpiar_previsualizacion() -> None:
    st.session_state.pop(_PREVIEW_KEY, None)
    st.session_state.pop(_PATHS_KEY, None)
    st.session_state.pop(_CODE_KEY, None)


def mostrar_cotizacion() -> None:
    st.title("Registrar cotización")
    st.caption(
        "Sube una o varias imágenes pertenecientes a "
        "la misma cotización."
    )

    last_result = st.session_state.get(_RESULT_KEY)

    if last_result is not None:
        st.success(
            f"Cotización {last_result['document_id']} "
            "registrada correctamente."
        )

        with st.expander("Ver resultado del registro"):
            st.json(last_result)

    preview = st.session_state.get(_PREVIEW_KEY)
    has_preview = isinstance(preview, ExtraccionDocumento)

    quotation_code = st.text_input(
        "Código interno de cotización",
        placeholder="Ejemplo: COT-2026-001",
        disabled=has_preview,
    )

    uploaded_files = st.file_uploader(
        "Imágenes de la cotización",
        type=[
            "jpg",
            "jpeg",
            "jpe",
            "jfif",
            "png",
            "webp",
            "bmp",
            "tif",
            "tiff",
            "gif",
        ],
        accept_multiple_files=True,
        disabled=has_preview,
        help=(
            "Selecciona todas las imágenes que pertenezcan "
            "al mismo documento."
        ),
    )

    if not has_preview:
        if st.button(
            "Analizar cotización",
            type="primary",
            use_container_width=True,
        ):
            normalized_code = quotation_code.strip().upper()

            if not normalized_code:
                st.error(
                    "Ingresa el código interno de cotización."
                )
                return

            if not uploaded_files:
                st.error(
                    "Selecciona al menos una imagen."
                )
                return

            try:
                image_paths = guardar_archivos_cargados(
                    uploaded_files
                )
                context = obtener_contexto_aplicacion()

                with st.spinner(
                    "Analizando la cotización con Cohere..."
                ):
                    extraction = (
                        context.agent.previsualizar_extraccion(
                            TipoDocumento.QUOTATION,
                            image_paths,
                        )
                    )
            except (ErrorAgenteComprobantes, OSError, ValueError) as exc:
                st.error(f"No se pudo analizar: {exc}")
                return

            st.session_state[_PREVIEW_KEY] = extraction
            st.session_state[_PATHS_KEY] = image_paths
            st.session_state[_CODE_KEY] = normalized_code
            st.session_state.pop(_RESULT_KEY, None)
            st.rerun()

        return

    image_paths = st.session_state.get(_PATHS_KEY, [])
    confirmed_code = st.session_state.get(_CODE_KEY, "")

    st.info(
        f"Revisando la cotización: {confirmed_code}"
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
        _limpiar_previsualizacion()
        st.rerun()

    confirmed_extraction = mostrar_editor_extraccion(
        preview,
        key_prefix="quotation",
    )

    if confirmed_extraction is None:
        return

    try:
        context = obtener_contexto_aplicacion()

        with st.spinner("Registrando cotización..."):
            result = context.agent.registrar_cotizacion(
                confirmed_code,
                image_paths,
                confirmed_extraction=confirmed_extraction,
            )
    except (ErrorAgenteComprobantes, OSError, ValueError) as exc:
        st.error(f"No se pudo registrar: {exc}")
        return

    st.session_state[_RESULT_KEY] = result.model_dump(
        mode="json"
    )
    _limpiar_previsualizacion()
    st.rerun()
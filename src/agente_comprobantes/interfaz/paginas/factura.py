from __future__ import annotations

from pathlib import Path
from time import perf_counter

import streamlit as st

from agente_comprobantes.dominio import (
    ExtraccionDocumento,
    RegistroCotizacion,
    TipoDocumento,
)
from agente_comprobantes.excepciones import ErrorAgenteComprobantes
from agente_comprobantes.interfaz.cargas import guardar_archivos_cargados
from agente_comprobantes.interfaz.componentes.editor_extraccion import (
    mostrar_editor_extraccion,
)
from agente_comprobantes.interfaz.componentes.resultados_factura import mostrar_resultado_factura
from agente_comprobantes.interfaz.contexto import obtener_contexto_aplicacion

_PREVIEW_KEY = "_invoice_preview"
_PATHS_KEY = "_invoice_paths"
_QUOTATION_KEY = "_invoice_quotation_code"
_RESULT_KEY = "_invoice_result"
_ELAPSED_KEY = "_invoice_elapsed_seconds"


def _limpiar_previsualizacion() -> None:
    st.session_state.pop(_PREVIEW_KEY, None)
    st.session_state.pop(_PATHS_KEY, None)
    st.session_state.pop(_QUOTATION_KEY, None)
    st.session_state.pop(_ELAPSED_KEY, None)


def _etiqueta_cotizacion(
    quotation: RegistroCotizacion,
) -> str:
    provider = quotation.provider or "Proveedor no identificado"

    if quotation.quoted_amount is None:
        amount = "sin monto"
    else:
        currency = (
            quotation.currency.value
            if quotation.currency is not None
            else ""
        )
        amount = (
            f"{currency} "
            f"{quotation.quoted_amount:,.2f}"
        ).strip()

    return (
        f"{quotation.quotation_code} | "
        f"{provider} | {amount}"
    )


def mostrar_factura() -> None:
    st.title("Registrar factura")
    st.caption(
        "Selecciona la cotización relacionada y sube "
        "una o varias imágenes de la factura."
    )

    last_result = st.session_state.get(_RESULT_KEY)

    if isinstance(last_result, dict):
        mostrar_resultado_factura(last_result)

    context = obtener_contexto_aplicacion()
    quotations = context.repository.listar_cotizaciones()

    if not quotations:
        st.warning(
            "No existen cotizaciones registradas. "
            "Registra una cotización antes de procesar "
            "una factura."
        )
        return

    quotation_by_code = {
        quotation.quotation_code: quotation
        for quotation in quotations
    }
    quotation_codes = list(quotation_by_code)

    preview = st.session_state.get(_PREVIEW_KEY)
    has_preview = isinstance(
        preview,
        ExtraccionDocumento,
    )

    selected_code = st.selectbox(
        "Cotización relacionada",
        options=quotation_codes,
        format_func=lambda code: _etiqueta_cotizacion(
            quotation_by_code[code]
        ),
        disabled=has_preview,
        help=(
            "La factura se comparará únicamente con "
            "la cotización seleccionada."
        ),
    )

    selected_quotation = quotation_by_code[
        selected_code
    ]

    if not has_preview:
        st.info(
            "Cotización seleccionada: "
            f"{_etiqueta_cotizacion(selected_quotation)}"
        )

    uploaded_files = st.file_uploader(
        "Imágenes de la factura",
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
            "a la misma factura."
        ),
    )

    if not has_preview:
        if st.button(
            "Analizar factura",
            type="primary",
            use_container_width=True,
        ):
            if not uploaded_files:
                st.error(
                    "Selecciona al menos una imagen."
                )
                return

            started_at = perf_counter()

            try:
                image_paths = guardar_archivos_cargados(
                    uploaded_files
                )

                with st.spinner(
                    "Analizando la factura con el proveedor "
                    "de visión disponible..."
                ):
                    extraction = (
                        context.agent.previsualizar_extraccion(
                            TipoDocumento.INVOICE,
                            image_paths,
                        )
                    )
            except (
                ErrorAgenteComprobantes,
                OSError,
                ValueError,
            ) as exc:
                elapsed = perf_counter() - started_at
                st.error(
                    "No se pudo analizar la factura "
                    f"después de {elapsed:.1f} segundos: "
                    f"{exc}"
                )
                return

            elapsed = perf_counter() - started_at

            st.session_state[_PREVIEW_KEY] = extraction
            st.session_state[_PATHS_KEY] = image_paths
            st.session_state[_QUOTATION_KEY] = (
                selected_code
            )
            st.session_state[_ELAPSED_KEY] = elapsed
            st.session_state.pop(_RESULT_KEY, None)
            st.rerun()

        return

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
        _limpiar_previsualizacion()
        st.rerun()

    confirmed_extraction = mostrar_editor_extraccion(
        preview,
        key_prefix="invoice",
    )

    if confirmed_extraction is None:
        return

    try:
        with st.spinner(
            "Registrando y comparando la factura..."
        ):
            result = context.agent.registrar_factura(
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
    _limpiar_previsualizacion()
    st.rerun()
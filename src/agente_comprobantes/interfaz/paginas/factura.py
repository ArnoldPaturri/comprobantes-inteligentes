from __future__ import annotations

from pathlib import Path
from time import perf_counter

import streamlit as st

from invoice_agent.domain import (
    DocumentExtraction,
    DocumentType,
    QuotationRecord,
)
from invoice_agent.exceptions import InvoiceAgentError
from invoice_agent.ui.components.extraction_editor import (
    render_extraction_editor,
)
from invoice_agent.ui.components.resultados_factura import mostrar_resultado_factura
from invoice_agent.ui.context import get_app_context
from invoice_agent.ui.uploads import save_uploaded_files

_PREVIEW_KEY = "_invoice_preview"
_PATHS_KEY = "_invoice_paths"
_QUOTATION_KEY = "_invoice_quotation_code"
_RESULT_KEY = "_invoice_result"
_ELAPSED_KEY = "_invoice_elapsed_seconds"


def _clear_preview() -> None:
    st.session_state.pop(_PREVIEW_KEY, None)
    st.session_state.pop(_PATHS_KEY, None)
    st.session_state.pop(_QUOTATION_KEY, None)
    st.session_state.pop(_ELAPSED_KEY, None)


def _quotation_label(
    quotation: QuotationRecord,
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


def render_invoice() -> None:
    st.title("Registrar factura")
    st.caption(
        "Selecciona la cotización relacionada y sube "
        "una o varias imágenes de la factura."
    )

    last_result = st.session_state.get(_RESULT_KEY)

    if isinstance(last_result, dict):
        mostrar_resultado_factura(last_result)

    context = get_app_context()
    quotations = context.repository.list_quotations()

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
        DocumentExtraction,
    )

    selected_code = st.selectbox(
        "Cotización relacionada",
        options=quotation_codes,
        format_func=lambda code: _quotation_label(
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
            f"{_quotation_label(selected_quotation)}"
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
                image_paths = save_uploaded_files(
                    uploaded_files
                )

                with st.spinner(
                    "Analizando la factura con el proveedor "
                    "de visión disponible..."
                ):
                    extraction = (
                        context.agent.preview_extraction(
                            DocumentType.INVOICE,
                            image_paths,
                        )
                    )
            except (
                InvoiceAgentError,
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
        _clear_preview()
        st.rerun()

    confirmed_extraction = render_extraction_editor(
        preview,
        key_prefix="invoice",
    )

    if confirmed_extraction is None:
        return

    try:
        with st.spinner(
            "Registrando y comparando la factura..."
        ):
            result = context.agent.register_invoice(
                confirmed_code,
                image_paths,
                confirmed_extraction=confirmed_extraction,
            )
    except (
        InvoiceAgentError,
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
    _clear_preview()
    st.rerun()
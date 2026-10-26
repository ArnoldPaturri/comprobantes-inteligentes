from __future__ import annotations

import streamlit as st

from agente_comprobantes.dominio import (
    ExtraccionDocumento,
    TipoDocumento,
)
from agente_comprobantes.excepciones import ErrorAgenteComprobantes
from agente_comprobantes.interfaz.cargas import guardar_archivos_cargados
from agente_comprobantes.interfaz.componentes.etiquetas_pago import (
    etiqueta_cotizacion,
    etiqueta_factura,
)
from agente_comprobantes.interfaz.componentes.resultados_pago import mostrar_resultado_pago
from agente_comprobantes.interfaz.contexto import obtener_contexto_aplicacion
from agente_comprobantes.interfaz.flujos.pago import (
    _INVOICE_KEY,
    _MODE_WITH_INVOICE,
    _MODE_WITHOUT_INVOICE,
    _MODE_KEY,
    _PATHS_KEY,
    _PREVIEW_KEY,
    _QUOTATION_KEY,
    _RESULT_KEY,
    limpiar_previsualizacion,
    mostrar_revision_pago,
)


def mostrar_pago() -> None:
    st.title("Registrar pago")
    st.caption(
        "Registra transferencias, depósitos, Yape, Plin "
        "u otras constancias de pago."
    )

    context = obtener_contexto_aplicacion()
    quotations = context.repository.listar_cotizaciones()

    if not quotations:
        st.warning(
            "Primero debes registrar al menos una cotización."
        )
        return

    last_result = st.session_state.get(_RESULT_KEY)

    if isinstance(last_result, dict):
        mostrar_resultado_pago(last_result)

        if st.button(
            "Registrar otro pago",
            use_container_width=True,
        ):
            st.session_state.pop(_RESULT_KEY, None)
            limpiar_previsualizacion()
            st.rerun()

        return

    preview = st.session_state.get(_PREVIEW_KEY)
    has_preview = isinstance(
        preview,
        ExtraccionDocumento,
    )

    quotation_by_code = {
        quotation.quotation_code: quotation
        for quotation in quotations
    }
    quotation_codes = list(quotation_by_code)

    selected_quotation_code = st.selectbox(
        "Cotización relacionada",
        options=quotation_codes,
        format_func=lambda code: etiqueta_cotizacion(
            quotation_by_code[code]
        ),
        disabled=has_preview,
    )

    mode = st.radio(
        "¿La factura ya fue registrada?",
        options=[
            _MODE_WITH_INVOICE,
            _MODE_WITHOUT_INVOICE,
        ],
        disabled=has_preview,
        help=(
            "Si la factura todavía no existe, el pago quedará "
            "pendiente y podrá vincularse posteriormente."
        ),
    )

    selected_invoice_id: str | None = None

    if mode == _MODE_WITH_INVOICE:
        invoices = context.repository.listar_facturas(
            selected_quotation_code
        )
        invoice_by_id = {
            invoice.invoice_id: invoice
            for invoice in invoices
            if invoice.payment_status.value != "PAGADO"
        }

        if invoice_by_id:
            selected_invoice_id = st.selectbox(
                "Factura que se está pagando",
                options=list(invoice_by_id),
                format_func=lambda invoice_id: etiqueta_factura(
                    invoice_by_id[invoice_id]
                ),
                disabled=has_preview,
            )
        else:
            st.warning(
                "Esta cotización no tiene facturas pendientes "
                "disponibles. Puedes registrar el pago como "
                "pendiente de factura."
            )

    uploaded_files = st.file_uploader(
        "Imágenes del comprobante de pago",
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
            "al mismo comprobante."
        ),
    )

    if not has_preview:
        if st.button(
            "Analizar comprobante de pago",
            type="primary",
            use_container_width=True,
        ):
            if (
                mode == _MODE_WITH_INVOICE
                and selected_invoice_id is None
            ):
                st.error(
                    "Selecciona una factura o registra el pago "
                    "como pendiente de factura."
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

                with st.spinner(
                    "Analizando el comprobante de pago..."
                ):
                    extraction = (
                        context.agent.previsualizar_extraccion(
                            TipoDocumento.PAYMENT_RECEIPT,
                            image_paths,
                        )
                    )
            except (
                ErrorAgenteComprobantes,
                OSError,
                ValueError,
            ) as exc:
                st.error(
                    f"No se pudo analizar el pago: {exc}"
                )
                return

            st.session_state[_PREVIEW_KEY] = extraction
            st.session_state[_PATHS_KEY] = image_paths
            st.session_state[
                _QUOTATION_KEY
            ] = selected_quotation_code
            st.session_state[
                _INVOICE_KEY
            ] = selected_invoice_id
            st.session_state[_MODE_KEY] = mode
            st.session_state.pop(_RESULT_KEY, None)
            st.rerun()

        return

    mostrar_revision_pago(preview, context)

from __future__ import annotations

from pathlib import Path

import streamlit as st

from agente_comprobantes.dominio import (
    ExtraccionDocumento,
    RegistroCotizacion,
    RegistroFactura,
    TipoDocumento,
)
from agente_comprobantes.excepciones import ErrorAgenteComprobantes
from agente_comprobantes.interfaz.cargas import save_uploaded_files
from agente_comprobantes.interfaz.componentes.editor_extraccion import (
    render_extraction_editor,
)
from agente_comprobantes.interfaz.componentes.resultados_pago import mostrar_resultado_pago
from agente_comprobantes.interfaz.contexto import get_app_context

_PREVIEW_KEY = "_payment_preview"
_PATHS_KEY = "_payment_paths"
_QUOTATION_KEY = "_payment_quotation"
_INVOICE_KEY = "_payment_invoice"
_MODE_KEY = "_payment_mode"
_RESULT_KEY = "_payment_result"

_MODE_WITH_INVOICE = "Aplicar a una factura existente"
_MODE_WITHOUT_INVOICE = "Registrar antes de recibir la factura"


def _clear_preview() -> None:
    st.session_state.pop(_PREVIEW_KEY, None)
    st.session_state.pop(_PATHS_KEY, None)
    st.session_state.pop(_QUOTATION_KEY, None)
    st.session_state.pop(_INVOICE_KEY, None)
    st.session_state.pop(_MODE_KEY, None)


def _quotation_label(
    quotation: RegistroCotizacion,
) -> str:
    provider = quotation.provider or "Proveedor no identificado"
    amount = (
        f"{quotation.currency.value} {quotation.quoted_amount:,.2f}"
        if quotation.currency is not None
        and quotation.quoted_amount is not None
        else "Monto no disponible"
    )

    return (
        f"{quotation.quotation_code} | "
        f"{provider} | "
        f"{amount}"
    )


def _invoice_label(
    invoice: RegistroFactura,
) -> str:
    number = invoice.invoice_number or "Sin número"
    amount = (
        f"{invoice.currency.value} {invoice.invoiced_amount:,.2f}"
        if invoice.currency is not None
        and invoice.invoiced_amount is not None
        else "Monto no disponible"
    )

    return (
        f"{invoice.invoice_id} | "
        f"{number} | "
        f"{amount} | "
        f"{invoice.payment_status.value}"
    )


def render_payment() -> None:
    st.title("Registrar pago")
    st.caption(
        "Registra transferencias, depósitos, Yape, Plin "
        "u otras constancias de pago."
    )

    context = get_app_context()
    quotations = context.repository.list_quotations()

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
            _clear_preview()
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
        format_func=lambda code: _quotation_label(
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
        invoices = context.repository.list_invoices(
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
                format_func=lambda invoice_id: _invoice_label(
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
                image_paths = save_uploaded_files(
                    uploaded_files
                )

                with st.spinner(
                    "Analizando el comprobante de pago..."
                ):
                    extraction = (
                        context.agent.preview_extraction(
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
        _clear_preview()
        st.rerun()

    confirmed_extraction = render_extraction_editor(
        preview,
        key_prefix="payment",
    )

    if confirmed_extraction is None:
        return

    try:
        with st.spinner("Registrando el pago..."):
            result = context.agent.register_payment(
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
    _clear_preview()
    st.rerun()
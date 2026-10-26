from __future__ import annotations

from typing import Any

import streamlit as st

from agente_comprobantes.dominio import (
    Moneda,
    ExtraccionDocumento,
)


def _as_text(value: Any) -> str:
    return "" if value is None else str(value)


def render_extraction_editor(
    extraction: ExtraccionDocumento,
    *,
    key_prefix: str,
) -> ExtraccionDocumento | None:
    if extraction.uncertain_fields:
        st.warning(
            "Campos que requieren revisión: "
            + ", ".join(extraction.uncertain_fields)
        )

    if extraction.observations:
        with st.expander("Observaciones de la extracción"):
            for observation in extraction.observations:
                st.write(f"- {observation}")

    currency_options = [
        "",
        *(currency.value for currency in Moneda),
    ]
    current_currency = (
        extraction.currency.value
        if extraction.currency is not None
        else ""
    )

    with st.form(f"{key_prefix}_extraction_form"):
        st.subheader("Revisar información extraída")

        st.text_input(
            "Tipo de documento",
            value=extraction.document_type.value,
            disabled=True,
        )

        provider_column, tax_id_column = st.columns(2)

        with provider_column:
            provider = st.text_input(
                "Proveedor o beneficiario",
                value=_as_text(extraction.provider),
            )

        with tax_id_column:
            provider_tax_id = st.text_input(
                "RUC del proveedor",
                value=_as_text(extraction.provider_tax_id),
            )

        concept = st.text_area(
            "Concepto o descripción",
            value=_as_text(extraction.concept),
        )

        number_column, date_column = st.columns(2)

        with number_column:
            document_number = st.text_input(
                "Número del documento",
                value=_as_text(extraction.document_number),
            )

        with date_column:
            document_date = st.text_input(
                "Fecha del documento",
                value=_as_text(extraction.document_date),
                help="Utiliza el formato YYYY-MM-DD.",
            )

        raw_amount_column, amount_column, currency_column = st.columns(3)

        with raw_amount_column:
            total_amount_raw = st.text_input(
                "Monto tal como aparece",
                value=_as_text(extraction.total_amount_raw),
            )

        with amount_column:
            total_amount = st.text_input(
                "Monto normalizado",
                value=_as_text(extraction.total_amount),
            )

        with currency_column:
            currency = st.selectbox(
                "Moneda",
                options=currency_options,
                index=currency_options.index(current_currency),
            )

        with st.expander("Campos adicionales"):
            operation_number = st.text_input(
                "Número de operación",
                value=_as_text(extraction.operation_number),
            )
            payment_entity = st.text_input(
                "Banco o entidad de pago",
                value=_as_text(extraction.payment_entity),
            )
            quotation_reference = st.text_input(
                "Referencia de cotización",
                value=_as_text(extraction.quotation_reference),
            )

        st.caption(
            f"Confianza declarada por el modelo: "
            f"{extraction.confidence:.0%}"
        )

        submitted = st.form_submit_button(
            "Confirmar y registrar",
            type="primary",
            use_container_width=True,
        )

    if not submitted:
        return None

    payload = extraction.model_dump(mode="python")
    payload.update(
        {
            "provider": provider or None,
            "provider_tax_id": provider_tax_id or None,
            "concept": concept or None,
            "document_number": document_number or None,
            "document_date": document_date or None,
            "total_amount_raw": total_amount_raw or None,
            "total_amount": total_amount or None,
            "currency": currency or None,
            "operation_number": operation_number or None,
            "payment_entity": payment_entity or None,
            "quotation_reference": quotation_reference or None,
        }
    )

    payload["uncertain_fields"] = [
        field
        for field in extraction.uncertain_fields
        if payload.get(field) in (None, "")
    ]

    try:
        return ExtraccionDocumento.model_validate(payload)
    except ValueError as exc:
        st.error(
            "Revisa los valores ingresados: "
            f"{exc}"
        )
        return None
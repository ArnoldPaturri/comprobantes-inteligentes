from __future__ import annotations

from typing import Any

import streamlit as st


def mostrar_resultado_factura(result: dict[str, Any]) -> None:
    status = result.get(
        "verification_status",
        "DESCONOCIDO",
    )
    document_id = result.get("document_id", "")

    if status == "VERIFICADO":
        st.success(
            f"Factura {document_id} registrada y verificada."
        )
    else:
        st.warning(
            f"Factura {document_id} registrada con estado "
            f"{status}."
        )

    reconciliation = result.get("reconciliation")

    if isinstance(reconciliation, dict):
        st.subheader("Resultado de la comparación")

        quoted_column, invoiced_column, difference_column = (
            st.columns(3)
        )

        quoted_column.metric(
            "Monto cotizado",
            reconciliation.get("quoted_amount") or "—",
        )
        invoiced_column.metric(
            "Monto facturado",
            reconciliation.get("invoiced_amount") or "—",
        )
        difference_column.metric(
            "Diferencia",
            reconciliation.get("difference") or "—",
        )

        diagnosis = reconciliation.get("diagnosis")
        deviation = reconciliation.get(
            "deviation_percent"
        )
        similarity = reconciliation.get(
            "provider_similarity"
        )

        if diagnosis:
            st.info(f"Diagnóstico: {diagnosis}")

        details: list[str] = []

        if deviation is not None:
            details.append(
                f"Desvío: {deviation}%"
            )

        if similarity is not None:
            details.append(
                "Similitud del proveedor: "
                f"{float(similarity):.0%}"
            )

        if details:
            st.caption(" · ".join(details))

        issues = reconciliation.get("issues") or []

        for issue in issues:
            if isinstance(issue, dict):
                st.warning(
                    issue.get(
                        "message",
                        "La conciliación requiere revisión.",
                    )
                )

    with st.expander("Ver respuesta completa"):
        st.json(result)

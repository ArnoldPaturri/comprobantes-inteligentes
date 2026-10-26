from __future__ import annotations

import streamlit as st


def mostrar_resultado_pago(result: dict[str, object]) -> None:
    verification_status = str(
        result.get("verification_status", "")
    )
    document_id = str(result.get("document_id", ""))

    if verification_status == "VERIFICADO":
        st.success(
            f"Pago {document_id} registrado correctamente."
        )
    else:
        st.warning(
            f"Pago {document_id} registrado con estado "
            f"{verification_status}."
        )

    reconciliation = result.get(
        "payment_reconciliation"
    )

    if not isinstance(reconciliation, dict):
        st.info(
            "El pago quedó pendiente hasta que se registre "
            "la factura correspondiente."
        )
    else:
        st.subheader("Resultado de la conciliación")

        first, second, third = st.columns(3)

        with first:
            st.metric(
                "Monto de la factura",
                reconciliation.get(
                    "invoice_amount",
                    "No disponible",
                ),
            )

        with second:
            st.metric(
                "Pago detectado",
                reconciliation.get(
                    "current_payment_amount",
                    "No disponible",
                ),
            )

        with third:
            st.metric(
                "Saldo pendiente",
                reconciliation.get(
                    "remaining_amount",
                    "No disponible",
                ),
            )

        applied = reconciliation.get("applied", False)
        payment_status = reconciliation.get(
            "resulting_payment_status",
            "No disponible",
        )

        if applied:
            st.success(
                f"Pago aplicado. Estado resultante: "
                f"{payment_status}."
            )
        else:
            st.warning(
                "El pago fue registrado, pero no se aplicó "
                "automáticamente a la factura."
            )

        issues = reconciliation.get("issues", [])

        if isinstance(issues, list):
            for issue in issues:
                if isinstance(issue, dict):
                    st.warning(
                        str(
                            issue.get(
                                "message",
                                "Requiere revisión.",
                            )
                        )
                    )

    with st.expander("Ver resultado completo"):
        st.json(result)

import streamlit as st


def render_home() -> None:
    st.title("Agente de comprobantes")
    st.caption(
        "Extracción, verificación y conciliación documental "
        "asistida por inteligencia artificial."
    )

    st.info(
        "Utiliza la navegación para registrar cotizaciones, "
        "facturas y pagos."
    )

    st.subheader("Flujo de trabajo")

    quotation_column, invoice_column, payment_column = st.columns(3)

    with quotation_column:
        st.markdown("### 1. Cotización")
        st.write(
            "Registra el documento inicial y su monto cotizado."
        )

    with invoice_column:
        st.markdown("### 2. Factura")
        st.write(
            "Relaciona la factura y compara sus importes."
        )

    with payment_column:
        st.markdown("### 3. Pago")
        st.write(
            "Registra o vincula el comprobante del pago."
        )

    st.divider()

    st.success(
        "El backend está preparado para validar documentos, "
        "detectar duplicados y evitar pagos dudosos."
    )
import streamlit as st

from invoice_agent.ui.pages.home import render_home
from invoice_agent.ui.pages.invoice import render_invoice
from invoice_agent.ui.pages.payment import render_payment
from invoice_agent.ui.pages.quotation import render_quotation

st.set_page_config(
    page_title="Agente de comprobantes",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="expanded",
)

pages = {
    "General": [
        st.Page(
            render_home,
            title="Inicio",
            icon="🏠",
            default=True,
        ),
    ],
    "Documentos": [
        st.Page(
            render_quotation,
            title="Registrar cotización",
            icon="📄",
        ),
        st.Page(
            render_invoice,
            title="Registrar factura",
            icon="🧾",
        ),
        st.Page(
            render_payment,
            title="Registrar pago",
            icon="💰",
        ),
    ],
}

current_page = st.navigation(
    pages,
    position="sidebar",
)

current_page.run()
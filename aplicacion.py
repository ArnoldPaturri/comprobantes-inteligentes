import streamlit as st

from agente_comprobantes.interfaz.paginas.cotizacion import render_quotation
from agente_comprobantes.interfaz.paginas.factura import render_invoice
from agente_comprobantes.interfaz.paginas.inicio import render_home
from agente_comprobantes.interfaz.paginas.pago import render_payment

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
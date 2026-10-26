import streamlit as st

from agente_comprobantes.interfaz.paginas.cotizacion import mostrar_cotizacion
from agente_comprobantes.interfaz.paginas.factura import mostrar_factura
from agente_comprobantes.interfaz.paginas.inicio import mostrar_inicio
from agente_comprobantes.interfaz.paginas.pago import mostrar_pago

st.set_page_config(
    page_title="Agente de comprobantes",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="expanded",
)

pages = {
    "General": [
        st.Page(
            mostrar_inicio,
            title="Inicio",
            icon="🏠",
            default=True,
        ),
    ],
    "Documentos": [
        st.Page(
            mostrar_cotizacion,
            title="Registrar cotización",
            icon="📄",
        ),
        st.Page(
            mostrar_factura,
            title="Registrar factura",
            icon="🧾",
        ),
        st.Page(
            mostrar_pago,
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
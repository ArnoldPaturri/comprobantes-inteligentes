import streamlit as st

from agente_comprobantes.interfaz.estilos import aplicar_estilos
from agente_comprobantes.interfaz.paginas.control_fletes import mostrar_control_fletes
from agente_comprobantes.interfaz.paginas.cotizacion import mostrar_cotizacion
from agente_comprobantes.interfaz.paginas.factura import mostrar_factura
from agente_comprobantes.interfaz.paginas.inicio import mostrar_inicio
from agente_comprobantes.interfaz.paginas.pago import mostrar_pago

st.set_page_config(
    page_title="Comprobantes Inteligentes",
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
    "Control y seguimiento": [
        st.Page(
            mostrar_control_fletes,
            title="Control financiero",
            icon="📊",
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

aplicar_estilos()

current_page = st.navigation(
    pages,
    position="sidebar",
)

current_page.run()
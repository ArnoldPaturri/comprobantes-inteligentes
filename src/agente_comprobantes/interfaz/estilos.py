"""Identidad de Comprobantes Inteligentes, inspirada en la paleta de Odoo."""

import streamlit as st

ESTILOS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"], [data-testid="stApp"] {
    font-family: Inter, "Segoe UI", sans-serif;
}
[data-testid="stSidebar"] {
    background: #F1EDF1;
    border-right: 1px solid #E9E1E8;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
    color: #443847;
}
.block-container {padding-top: 1.25rem; padding-bottom: 2rem;}
[data-testid="stMetric"] {
    background: #FFFFFF;
    border: 1px solid #E7E2E8;
    border-radius: 13px;
    padding: 11px 15px;
    box-shadow: 0 2px 12px rgb(44 31 49 / 3%);
}
[data-testid="stMetricLabel"] {color: #655A69;}
[data-testid="stMetricValue"] {font-weight: 700; color: #34233A;}
.stButton > button[kind="primary"] {
    background: #714B67;
    border-color: #714B67;
    border-radius: 8px;
}
div[data-testid="stDataFrame"] {
    border: 1px solid #E7E2E8;
    border-radius: 10px;
    overflow: hidden;
}
.ci-hero {
    background: linear-gradient(113deg, #714B67 0%, #513B59 76%, #017E84 170%);
    color: #FFFFFF;
    border-radius: 15px;
    padding: 15px 23px;
    margin-bottom: 12px;
}
.ci-hero .ci-kicker {
    color: #CDE5E4;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.10em;
    text-transform: uppercase;
    margin-bottom: 7px;
}
.ci-hero h1 {color: white; font-size: 1.4rem; margin: 0 0 4px;}
.ci-hero p {color: #F5EEF4; margin: 0; font-size: 0.88rem;}
</style>
"""


def aplicar_estilos() -> None:
    st.markdown(ESTILOS, unsafe_allow_html=True)


def mostrar_cabecera(titulo: str, descripcion: str, *, seccion: str) -> None:
    """El contenido de este componente debe ser texto fijo, no datos de usuarios."""
    from html import escape

    st.markdown(
        '<div class="ci-hero">'
        f'<div class="ci-kicker">{escape(seccion)}</div>'
        f"<h1>{escape(titulo)}</h1>"
        f"<p>{escape(descripcion)}</p>"
        "</div>",
        unsafe_allow_html=True,
    )

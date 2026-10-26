"""Vista y descarga de adjuntos de control financiero guardados localmente."""

from __future__ import annotations

import streamlit as st

from agente_comprobantes.configuracion import Configuracion
from agente_comprobantes.control_financiero.archivos import almacen_para_excel


def mostrar_respaldo(referencia: str | None, *, clave: str) -> None:
    """Nunca intenta abrir rutas heredadas ni nombres aportados por un usuario."""
    if not referencia or not referencia.startswith("adjunto:"):
        st.caption(
            "El comprobante original todavía no está adjuntado al control. "
            "El nombre importado del OCR no constituye un archivo disponible."
        )
        return
    try:
        datos, extension = almacen_para_excel(
            Configuracion().ruta_archivo_excel()
        ).abrir(referencia)
    except (ValueError, OSError) as exc:
        st.error(f"No se pudo abrir el adjunto: {exc}")
        return
    with st.expander("Ver comprobante adjunto", expanded=False):
        if extension in ("png", "jpg"):
            st.image(datos, use_container_width=True)
        else:
            try:
                st.pdf(datos, height=500)
            except (ImportError, RuntimeError):
                st.info("La vista previa PDF necesita streamlit[pdf]. Puedes descargarlo.")
        st.download_button(
            "Descargar copia",
            data=datos,
            file_name=f"comprobante.{extension}",
            mime=(
                "application/pdf" if extension == "pdf"
                else "image/png" if extension == "png" else "image/jpeg"
            ),
            key=f"descargar_{clave}",
        )

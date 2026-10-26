"""Carga masiva con vista previa y aprobación explícita del lote."""

import streamlit as st

from agente_comprobantes.configuracion import Configuracion
from agente_comprobantes.control_financiero.importacion_masiva import (
    confirmar_importacion,
    preparar_importacion,
)
from agente_comprobantes.control_financiero.repositorio_json import (
    RepositorioControlFletes,
)


def mostrar_importador_excel() -> None:
    """Nunca modifica el Excel subido ni el libro operativo del agente."""
    with st.expander("Importar operaciones desde Excel (.xlsx)"):
        st.caption(
            "Carga el registro de fletes y bancarizaciones. Primero verás una "
            "vista previa con duplicados y errores. Ningún expediente se guarda "
            "hasta confirmar expresamente la importación."
        )
        archivo = st.file_uploader(
            "Seleccionar archivo Excel",
            type=["xlsx"],
            max_upload_size=8,
            key="archivo_importacion_fletes",
        )
        if archivo is None:
            st.caption(
                "Se reconocen columnas como Proveedor, N° Factura, Moneda, "
                "Monto Facturado, Nº de Guía y Monto bancarizado."
            )
            return

        destino = RepositorioControlFletes(
            Configuracion().ruta_archivo_excel().with_name("control_fletes.json")
        )
        try:
            vista = preparar_importacion(archivo.getvalue(), destino)
        except (OSError, ValueError, KeyError) as exc:
            st.error(f"No se pudo preparar la importación: {exc}")
            return

        st.caption(
            f"Hoja reconocida: {vista.nombre_hoja} · "
            f"Encabezados en fila {vista.encabezado}"
        )
        disponibles = len(vista.listas)
        col1, col2, col3 = st.columns(3)
        col1.metric("Listas para importar", disponibles)
        col2.metric("Duplicadas", vista.duplicadas)
        col3.metric("Con errores", vista.errores)

        if vista.filas:
            tabla = [
                {
                    "Fila": item.fila,
                    "Estado": item.estado,
                    "Factura": item.factura,
                    "Proveedor": item.proveedor,
                    "Moneda": item.moneda,
                    "Monto": item.monto,
                    "Detalle / advertencia": " · ".join(item.detalles),
                }
                for item in vista.filas[:200]
            ]
            st.dataframe(tabla, hide_index=True, use_container_width=True)
            if len(vista.filas) > 200:
                st.info(
                    "Se muestran las primeras 200 filas. El lote completo "
                    "se valida antes de importarse."
                )
        else:
            st.info("La hoja encontrada no contiene operaciones.")

        st.warning(
            "La importación NO declara fletes confirmados, NO acredita pagos "
            "y NO registra detracciones como verificadas, incluso cuando "
            "la hoja de origen indique Conforme o SI."
        )
        confirmar = st.checkbox(
            "Revisé la vista previa y autorizo incorporar únicamente las "
            "operaciones nuevas y válidas al archivo de control independiente.",
            key="aceptar_importacion_fletes",
        )
        if st.button(
            f"Importar {disponibles} operaciones",
            type="primary",
            disabled=not confirmar or disponibles == 0,
            key="confirmar_importacion_fletes",
        ):
            try:
                total = confirmar_importacion(vista, destino)
            except (OSError, ValueError) as exc:
                st.error(f"No se aplicó la importación: {exc}")
                return
            st.session_state["_mensaje_revision"] = (
                f"Se incorporaron {total} operaciones nuevas al control. "
                "El Excel de origen no fue modificado."
            )
            st.rerun()

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
            vista = preparar_importacion(
                archivo.getvalue(), destino, nombre_archivo=archivo.name
            )
        except (OSError, ValueError, KeyError) as exc:
            st.error(f"No se pudo preparar la importación: {exc}")
            return

        st.caption(
            f"Hoja reconocida: {vista.nombre_hoja} · "
            f"Encabezados en fila {vista.encabezado}"
        )
        disponibles = len(vista.listas)
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Listas para importar", disponibles)
        col2.metric("Duplicadas", vista.duplicadas)
        col3.metric("Con errores", vista.errores)
        col4.metric("Omitidas sin importes", vista.omitidas)

        reconocidas = (
            len(vista.columnas_origen) - len(vista.columnas_no_reconocidas)
        )
        st.caption(
            f"Columnas del origen: {len(vista.columnas_origen)} · "
            f"Reconocidas: {reconocidas} · "
            f"Adicionales: {len(vista.columnas_no_reconocidas)}. "
            "Se conservarán los valores disponibles de todas ellas."
        )
        if vista.columnas_no_reconocidas:
            st.info(
                "Columnas adicionales conservadas sin interpretación automática: "
                + ", ".join(vista.columnas_no_reconocidas)
            )

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

        with st.expander("Revisar todos los campos originales del Excel"):
            st.caption(
                "Conservamos la fotografía de cada fila (incluidos valores "
                "de estado, diferencia, detracción y observaciones). "
                "Las fórmulas sin resultado calculado pueden aparecer vacías."
            )
            originales = [
                {"Fila": item.fila, "Estado de importación": item.estado,
                 **item.valores_origen}
                for item in vista.filas[:200]
            ]
            st.dataframe(
                originales, hide_index=True, use_container_width=True
            )

        st.warning(
            "La importación NO confirma fletes, NO acredita pagos y NO valida "
            "detracciones o notas de crédito. Las diferencias, estados y "
            "observaciones originales se conservan para auditoría, pero no "
            "se convierten automáticamente en resultados financieros. "
            "Si una factura figura en varias filas con distintos pagos, "
            "es necesario revisar cómo agruparlos antes de confirmar el lote."
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

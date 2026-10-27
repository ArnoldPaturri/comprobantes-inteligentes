"""Portada de control operativo, sin cargar proveedores de IA."""

import streamlit as st

from agente_comprobantes.configuracion import Configuracion
from agente_comprobantes.control_financiero.modelos import SituacionControl
from agente_comprobantes.control_financiero.presentacion import cargar_tablero
from agente_comprobantes.interfaz.estilos import mostrar_cabecera


def mostrar_inicio() -> None:
    mostrar_cabecera(
        "Comprobantes Inteligentes",
        "Centraliza tus documentos, revisa conciliaciones y detecta excepciones.",
        seccion="Panel / Resumen general",
    )
    with st.expander("Guía rápida: de documento a conciliación", expanded=True):
        st.markdown(
            """
            **Sigue este orden para evitar registros huérfanos:**

            1. **Registrar cotización:** sube la imagen, revisa los datos extraídos y confirma.
            2. **Registrar factura:** elige la cotización relacionada y revisa diferencias de importe.
            3. **Registrar pago (si corresponde):** sube la imagen del comprobante y revisa el resultado.
            4. **Control financiero:** crea el expediente desde la factura, clasifica la operación y añade sus evidencias.
            5. **Conciliar:** acredita únicamente los importes cuyo respaldo hayas revisado y genera los reportes.
            """
        )
        st.info(
            "Formatos: cotizaciones, facturas y pagos por OCR aceptan imágenes "
            "(PNG/JPG y formatos indicados en cada pantalla); la importación masiva "
            "acepta XLSX; los PDF se usan como evidencias y adjuntos financieros."
        )
        st.warning(
            "Importante: que la IA lea un importe o que un pago aparezca en Excel "
            "no significa que esté acreditado. La revisión documental es manual; "
            "la aplicación no consulta bancos ni SUNAT."
        )

    ruta = Configuracion().ruta_archivo_excel().with_name("control_fletes.json")
    try:
        tablero = cargar_tablero(ruta)
    except (OSError, ValueError) as exc:
        st.error(f"No fue posible leer el control de fletes: {exc}")
        return

    cantidad = len(tablero.operaciones)
    pendientes = sum(
        r.situacion == SituacionControl.PENDIENTE
        for r in tablero.resultados.values()
    )
    observadas = sum(
        r.situacion == SituacionControl.OBSERVADA
        for r in tablero.resultados.values()
    )
    conformes = sum(
        r.situacion == SituacionControl.CONFORME
        for r in tablero.resultados.values()
    )
    columnas = st.columns(4)
    columnas[0].metric("Controles de fletes", cantidad)
    columnas[1].metric("Pendientes", pendientes)
    columnas[2].metric("Observados", observadas)
    columnas[3].metric("Conformes", conformes)

    if not cantidad:
        st.info(
            "No hay controles financieros registrados. Importa el borrador de "
            "una factura y luego consulta su expediente en Control financiero."
        )
    else:
        st.info(
            "En el menú lateral, abre **Control financiero** para consultar "
            "operaciones, respaldos y diferencias por moneda."
        )

    st.subheader("Flujo de documentos")
    columnas = st.columns(3)
    with columnas[0]:
        st.markdown("**01 · Cotizaciones**")
        st.caption("Presupuestos, proveedores y montos de referencia.")
    with columnas[1]:
        st.markdown("**02 · Facturas**")
        st.caption("Captura y comparación con las cotizaciones.")
    with columnas[2]:
        st.markdown("**03 · Pagos**")
        st.caption("Comprobantes, vínculos y conciliación documental.")

    st.caption(
        "Los estados financieros reflejan evidencia registrada y revisada. "
        "No son consultas en línea a bancos ni SUNAT."
    )

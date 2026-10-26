"""Panel profesional de control de fletes, en modalidad solo lectura."""

from __future__ import annotations

from decimal import Decimal

import streamlit as st

from agente_comprobantes.configuracion import Configuracion
from agente_comprobantes.control_financiero.modelos import SituacionControl
from agente_comprobantes.control_financiero.presentacion import (
    cargar_tablero,
    formatear_importe,
)
from agente_comprobantes.dominio.enumeraciones import Moneda
from agente_comprobantes.interfaz.componentes.panel_evidencias import mostrar_evidencias
from agente_comprobantes.interfaz.estilos import mostrar_cabecera


def _mostrar_metricas(tablero, moneda: Moneda) -> None:
    resumen = next((r for r in tablero.resumenes if r.moneda == moneda), None)
    if resumen is None:
        return
    acreditado = sum(
        (
            r.total_acreditado
            for op in tablero.operaciones
            if op.moneda == moneda
            for r in (tablero.resultados[op.identificador],)
        ),
        Decimal("0"),
    )
    columnas = st.columns(4)
    columnas[0].metric(
        "Presupuesto identificado",
        formatear_importe(resumen.total_presupuestado, moneda),
    )
    columnas[1].metric(
        "Facturado con presupuesto",
        formatear_importe(resumen.facturado_con_presupuesto, moneda),
    )
    columnas[2].metric(
        "Acreditado documentalmente",
        formatear_importe(acreditado, moneda),
    )
    columnas[3].metric(
        "Exceso provisional",
        formatear_importe(resumen.exceso_acumulado_presupuesto, moneda),
    )
    st.caption(
        "El presupuesto se cuenta una vez por cotización. El exceso es provisional "
        "y no sustituye una evaluación de sobrecostos aprobados."
    )


def _mostrar_detalle(tablero, identificador: str) -> None:
    operacion = next(
        item for item in tablero.operaciones if item.identificador == identificador
    )
    resultado = tablero.resultados[identificador]
    st.subheader("Expediente documental")
    st.caption(
        f"{operacion.numero_factura} · {operacion.proveedor or 'Proveedor no identificado'}"
    )
    if resultado.situacion == SituacionControl.CONFORME:
        st.success("Documentalmente conforme. No equivale a validación bancaria.")
    elif resultado.situacion == SituacionControl.OBSERVADA:
        st.error("Operación observada: requiere revisión.")
    else:
        st.warning("Pendiente de completar y acreditar documentación.")

    izq, der = st.columns(2)
    izq.metric(
        "Facturado neto",
        formatear_importe(resultado.facturado_neto, operacion.moneda),
    )
    der.metric(
        "Sin acreditar documentalmente",
        formatear_importe(resultado.saldo_por_acreditar, operacion.moneda),
    )
    st.caption(
        "El saldo documental no representa necesariamente deuda pendiente de pago. "
        "Los comprobantes reconocidos por OCR pueden estar sin acreditar."
    )
    st.markdown("**Evidencias asociadas**")
    mostrar_evidencias(operacion)
    if resultado.observaciones:
        st.markdown("**Aspectos por revisar**")
        for observacion in resultado.observaciones:
            st.write(f"• {observacion}")
    else:
        st.info("Sin observaciones documentales en el control actual.")


def mostrar_control_fletes() -> None:
    mostrar_cabecera(
        "Control financiero de fletes",
        "Conciliación documental, evidencias y seguimiento de excepciones.",
        seccion="Operaciones / Control financiero",
    )
    configuracion = Configuracion()
    ruta = configuracion.ruta_archivo_excel().with_name("control_fletes.json")
    try:
        tablero = cargar_tablero(ruta)
    except (OSError, ValueError) as exc:
        st.error(f"No se pudieron consultar los controles: {exc}")
        return

    st.caption(f"Origen: {ruta.name} · Vista de consulta, sin modificaciones al Excel.")
    if not tablero.operaciones:
        st.info(
            "Aún no hay controles registrados. Crea un borrador desde una factura "
            "con el comando flete-borrador; luego podrás consultarlo aquí."
        )
        return

    st.warning(
        "Los borradores importados pueden corresponder a compras u otros servicios. "
        "Confirma que la operación sea un flete antes de asignarle reglas específicas."
    )

    monedas = sorted({operacion.moneda for operacion in tablero.operaciones}, key=str)
    c1, c2, c3 = st.columns([1, 1, 2])
    seleccion_moneda = c1.selectbox(
        "Moneda", options=monedas, format_func=lambda m: m.value
    )
    filtro_estado = c2.selectbox(
        "Estado", ["Todos", *[e.value for e in SituacionControl]]
    )
    busqueda = c3.text_input(
        "Buscar", placeholder="Factura, proveedor, guía o cotización..."
    )
    _mostrar_metricas(tablero, seleccion_moneda)

    estado = None if filtro_estado == "Todos" else SituacionControl(filtro_estado)
    filas = tablero.filas(seleccion_moneda, estado, busqueda)
    st.subheader("Operaciones registradas")
    st.caption(f"{len(filas)} resultado(s) · Importes en {seleccion_moneda.value}")
    if not filas:
        st.info("No hay operaciones con los filtros seleccionados.")
        return

    datos = [
        {
            "ID": fila.identificador,
            "Factura": fila.factura,
            "Proveedor": fila.proveedor,
            "Guía": fila.guia,
            "Facturado neto": formatear_importe(fila.facturado, fila.moneda),
            "Pago declarado": formatear_importe(fila.declarado, fila.moneda),
            "Acreditado": formatear_importe(fila.acreditado, fila.moneda),
            "Saldo documental": formatear_importe(fila.saldo_documental, fila.moneda),
            "Estado": fila.situacion.value,
        }
        for fila in filas
    ]
    st.dataframe(datos, use_container_width=True, hide_index=True)
    st.divider()
    identificador = st.selectbox(
        "Consultar expediente", [fila.identificador for fila in filas],
        format_func=lambda key: (
            f"{key} · {tablero.resultados[key].situacion.value}"
        ),
    )
    _mostrar_detalle(tablero, identificador)

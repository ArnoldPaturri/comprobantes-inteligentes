"""Panel de control financiero: selección directa y revisión documental."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import streamlit as st

from agente_comprobantes.configuracion import Configuracion
from agente_comprobantes.control_financiero.modelos import (
    OperacionFlete,
    SituacionControl,
)
from agente_comprobantes.control_financiero.presentacion import (
    TableroFletes,
    cargar_tablero,
    formatear_importe,
)
from agente_comprobantes.control_financiero.reporte_ejecutivo import exportar_excel_ejecutivo
from agente_comprobantes.control_financiero.reportes import exportar_control
from agente_comprobantes.control_financiero.repositorio_json import (
    RepositorioControlFletes,
)
from agente_comprobantes.control_financiero.revisiones import guardar_revision
from agente_comprobantes.dominio.enumeraciones import Moneda
from agente_comprobantes.interfaz.componentes.ajustes_financieros import (
    mostrar_ajustes_financieros,
)
from agente_comprobantes.interfaz.componentes.editor_incidencias import (
    mostrar_declaraciones_pendientes,
)
from agente_comprobantes.interfaz.componentes.importacion_excel import (
    mostrar_importador_excel,
)
from agente_comprobantes.interfaz.componentes.incidencias_existentes import (
    mostrar_incidencias_existentes,
)
from agente_comprobantes.interfaz.componentes.movimientos_centrales import (
    mostrar_movimientos_centrales,
)
from agente_comprobantes.interfaz.componentes.panel_evidencias import mostrar_evidencias
from agente_comprobantes.interfaz.componentes.revision_pagos import (
    mostrar_revision_pagos,
)
from agente_comprobantes.interfaz.estilos import mostrar_cabecera

CLASIFICACIONES = ("Sin clasificar", "Flete confirmado", "Otra operación")
DETRACCIONES = ("Por determinar", "Corresponde", "No corresponde")


def _mostrar_metricas(tablero: TableroFletes, moneda: Moneda) -> None:
    resumen = next((r for r in tablero.resumenes if r.moneda == moneda), None)
    if resumen is None:
        st.info(
            "No hay fletes confirmados en esta moneda. Clasifica las operaciones "
            "antes de incorporarlas a los indicadores financieros de transporte."
        )
        return
    acreditado = sum(
        (
            tablero.resultados[operacion.identificador].total_acreditado
            for operacion in tablero.operaciones
            if operacion.moneda == moneda and operacion.es_flete is True
        ),
        Decimal("0"),
    )
    columnas = st.columns(4)
    columnas[0].metric(
        "Presupuesto · fletes",
        formatear_importe(resumen.total_presupuestado, moneda),
    )
    columnas[1].metric(
        "Facturado · fletes",
        formatear_importe(resumen.facturado_con_presupuesto, moneda),
    )
    columnas[2].metric(
        "Acreditado documental",
        formatear_importe(acreditado, moneda),
    )
    columnas[3].metric(
        "Exceso provisional",
        formatear_importe(resumen.exceso_acumulado_presupuesto, moneda),
    )
    st.caption(
        "Solo fletes confirmados · Presupuestos no duplicados · "
        "Diferencias todavía sujetas a revisión."
    )


def _mostrar_expediente(tablero: TableroFletes, identificador: str) -> None:
    operacion = next(
        item for item in tablero.operaciones if item.identificador == identificador
    )
    resultado = tablero.resultados[identificador]
    st.subheader(f"Expediente · {operacion.numero_factura}")
    st.caption(
        f"{operacion.identificador} · "
        f"{operacion.proveedor or 'Proveedor no identificado'}"
    )

    if operacion.es_flete is None:
        st.warning(
            "Naturaleza de la operación por confirmar. No se incluye en "
            "los indicadores de fletes."
        )
    elif operacion.es_flete is False:
        st.info(
            "Clasificada como otra operación. Se conserva para trazabilidad, "
            "pero se excluye de los indicadores de transporte."
        )
    elif resultado.situacion == SituacionControl.CONFORME:
        st.success("Conformidad documental declarada; no es validación bancaria.")
    elif resultado.situacion == SituacionControl.OBSERVADA:
        st.error("Operación observada: requiere revisión.")
    else:
        st.warning("Pendiente de completar y revisar documentos.")

    detalle, gestion, pagos, ajustes = st.tabs(
        [
            "Documentación y diferencias",
            "Revisar expediente",
            "Revisar pagos",
            "Detracciones y notas",
        ]
    )
    with detalle:
        c1, c2, c3 = st.columns(3)
        pago_declarado = sum(
            (p.importe_aplicado for p in operacion.movimientos_bancarios),
            Decimal("0"),
        )
        c1.metric("Facturado neto", formatear_importe(resultado.facturado_neto, operacion.moneda))
        c2.metric("Pago declarado", formatear_importe(pago_declarado, operacion.moneda))
        c3.metric("Acreditado", formatear_importe(resultado.total_acreditado, operacion.moneda))
        st.caption(
            "El saldo documental no equivale necesariamente a deuda pendiente. "
            "Los pagos detectados por OCR se mantienen sin acreditar."
        )
        st.markdown("**Evidencias asociadas**")
        mostrar_evidencias(operacion)
        mostrar_declaraciones_pendientes(operacion)
        st.markdown("**Observaciones del control**")
        if resultado.observaciones:
            for observacion in resultado.observaciones:
                st.write(f"• {observacion}")
        else:
            st.caption("Sin observaciones documentales.")

        if operacion.revisiones:
            with st.expander(f"Historial local de revisiones ({len(operacion.revisiones)})"):
                for revision in reversed(operacion.revisiones):
                    st.write(revision.fecha.strftime("%Y-%m-%d %H:%M UTC"))
                    st.caption(revision.motivo)
                    st.json(revision.cambios)

    with gestion:
        _formulario_revision(operacion)
    with pagos:
        mostrar_revision_pagos(operacion)
    with ajustes:
        mostrar_ajustes_financieros(operacion)


def _formulario_revision(operacion: OperacionFlete) -> None:
    st.caption(
        "Esta revisión modifica únicamente control_fletes.json, no el Excel. "
        "No acredita pagos ni determina automáticamente obligaciones ante SUNAT."
    )
    opciones = {None: 0, True: 1, False: 2}
    with st.form(f"revisar_{operacion.identificador}"):
        tipo = st.selectbox(
            "Naturaleza de la operación",
            CLASIFICACIONES,
            index=opciones[operacion.es_flete],
        )
        guia = st.text_input(
            "N° de guía (si corresponde)",
            value=operacion.numero_guia or "",
            placeholder="Ej. EG07-642",
        )
        detraccion = st.selectbox(
            "Revisión de detracción (declaración manual)",
            DETRACCIONES,
            index=opciones[operacion.detraccion_aplica],
            help="Requiere revisión documental y tributaria; no se calcula automáticamente.",
        )
        motivo = st.text_area(
            "Sustento de la revisión",
            placeholder="Indica qué comprobante revisaste y por qué cambias el expediente.",
        )
        confirmado = st.checkbox(
            "Confirmo que he revisado la documentación y comprendo que "
            "esto no verifica movimientos en el banco ni en SUNAT."
        )
        enviado = st.form_submit_button("Guardar revisión", type="primary")
    if not enviado:
        return

    es_flete = (None, True, False)[CLASIFICACIONES.index(tipo)]
    aplica = (None, True, False)[DETRACCIONES.index(detraccion)]
    try:
        actualizado = guardar_revision(
            RepositorioControlFletes(
                Configuracion().ruta_archivo_excel().with_name("control_fletes.json")
            ),
            operacion.identificador,
            es_flete=es_flete,
            numero_guia=guia or None,
            detraccion_aplica=aplica,
            motivo=motivo,
            confirmacion=confirmado,
        )
    except (ValueError, OSError) as error:
        st.error(str(error))
        return

    st.session_state["_mensaje_revision"] = (
        f"Revisión guardada en el expediente {actualizado.identificador}."
    )
    st.rerun()


def mostrar_control_fletes() -> None:
    mostrar_cabecera(
        "Control financiero",
        "Documentos, conciliaciones y operaciones por revisar.",
        seccion="Operaciones / Control documental",
    )
    if mensaje := st.session_state.pop("_mensaje_revision", None):
        st.success(mensaje)
    ruta: Path = Configuracion().ruta_archivo_excel().with_name("control_fletes.json")
    try:
        tablero = cargar_tablero(ruta)
    except (ValueError, OSError) as error:
        st.error(f"No se pudieron leer los controles: {error}")
        return

    if not tablero.operaciones:
        st.info(
            "No hay expedientes registrados. Importa una factura con "
            "python principal.py flete-borrador --factura ID_FACTURA "
            "o utiliza el importador de Excel."
        )
        mostrar_importador_excel()
        return

    sin_clasificar = sum(op.es_flete is None for op in tablero.operaciones)
    st.caption(
        f"{len(tablero.operaciones)} expedientes · "
        f"{sin_clasificar} pendientes de clasificación · "
        "Archivo de control independiente del Excel."
    )

    monedas = sorted({op.moneda for op in tablero.operaciones}, key=str)
    c1, c2, c3 = st.columns([1, 1, 2])
    moneda = c1.selectbox("Moneda", monedas, format_func=lambda m: m.value)
    estado = c2.selectbox("Estado", ["Todos", *(e.value for e in SituacionControl)])
    busqueda = c3.text_input(
        "Buscar", placeholder="Factura, proveedor, guía o cotización..."
    )

    _mostrar_metricas(tablero, moneda)
    mostrar_importador_excel()
    mostrar_incidencias_existentes(tablero.operaciones)
    mostrar_movimientos_centrales(tablero.operaciones)
    st.subheader("Expedientes")
    filtro_estado = None if estado == "Todos" else SituacionControl(estado)
    filas = tablero.filas(moneda, filtro_estado, busqueda)
    st.download_button(
        "Descargar reporte para Excel (ZIP)",
        data=exportar_control(
            tablero, moneda=moneda, situacion=filtro_estado, busqueda=busqueda
        ),
        file_name="control_financiero_reporte.zip",
        mime="application/zip",
        help=(
            "Incluye operaciones, observaciones, historial y resumen por moneda. "
            "El resumen usa todos los fletes confirmados de la moneda elegida."
        ),
    )
    st.caption(
        "Cuatro archivos CSV compatibles con Excel. El resumen no aplica "
        "los filtros de estado ni búsqueda para no fraccionar presupuestos."
    )
    st.download_button(
        "Descargar informe ejecutivo (.xlsx)",
        data=exportar_excel_ejecutivo(
            tablero, moneda=moneda, situacion=filtro_estado, busqueda=busqueda
        ),
        file_name="comprobantes_inteligentes_resumen_ejecutivo.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        help=(
            "Libro de consulta con resumen ejecutivo, operaciones, observaciones "
            "e historial. No modifica el Excel original."
        ),
    )
    if not filas:
        st.info("Sin resultados con los filtros aplicados.")
        return

    tabla = [
        {
            "ID": fila.identificador,
            "Factura": fila.factura,
            "Proveedor": fila.proveedor,
            "Clasificación": fila.clasificacion,
            "Guía": fila.guia,
            "Facturado": formatear_importe(fila.facturado, fila.moneda),
            "Pago declarado": formatear_importe(fila.declarado, fila.moneda),
            "Acreditado": formatear_importe(fila.acreditado, fila.moneda),
            "Estado": fila.situacion.value,
        }
        for fila in filas
    ]
    seleccion = st.dataframe(
        tabla,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="tabla_controles",
    )
    elegidas = seleccion.selection.rows
    if not elegidas:
        st.caption("Selecciona una fila de la tabla para consultar o revisar su expediente.")
        return
    indice = elegidas[0]
    if 0 <= indice < len(filas):
        st.divider()
        _mostrar_expediente(tablero, filas[indice].identificador)

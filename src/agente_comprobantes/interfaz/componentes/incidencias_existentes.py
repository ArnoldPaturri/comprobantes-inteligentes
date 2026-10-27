"""Diagnóstico de expedientes existentes, independiente del importador."""

import streamlit as st

from agente_comprobantes.control_financiero.auditoria_expedientes import (
    auditar_expedientes,
)
from agente_comprobantes.control_financiero.modelos import OperacionFlete
from agente_comprobantes.interfaz.componentes.editor_incidencias import (
    mostrar_declaraciones_pendientes,
    mostrar_editor_incidencias,
)


def mostrar_incidencias_existentes(
    operaciones: list[OperacionFlete],
) -> None:
    """No modifica el JSON ni la acreditación documental de las operaciones."""
    hallazgos = auditar_expedientes(operaciones)
    with st.expander(
        f"Incidencias de expedientes ya registrados · {len(hallazgos)}",
        expanded=False,
    ):
        st.caption(
            "Esta consulta examina los registros guardados, no solo las filas "
            "del Excel subido. Los cambios del importador no corrigen "
            "retroactivamente movimientos o revisiones anteriores."
        )
        if not hallazgos:
            st.success(
                "No se detectaron etiquetas de efectivo ni referencias "
                "compartidas o múltiples en los expedientes actuales."
            )
            return
        st.dataframe(
            [
                {
                    "ID del expediente": h.identificador,
                    "Factura": h.factura,
                    "Proveedor": h.proveedor,
                    "Tipo": h.tipo,
                    "Referencia": h.referencia_original,
                    "Motivo": h.detalle,
                    "Qué revisar": h.accion,
                }
                for h in hallazgos
            ],
            hide_index=True,
            use_container_width=True,
        )
        st.info(
            "Puedes seleccionar un caso para revisar el expediente y corregir "
            "una referencia declarada. No se valida ningún movimiento bancario."
        )
        opciones = list(range(len(hallazgos)))
        seleccionado = st.selectbox(
            "Seleccionar incidencia para revisión",
            opciones,
            format_func=lambda i: (
                f"{hallazgos[i].factura} · {hallazgos[i].tipo}"
                f" · {hallazgos[i].identificador}"
            ),
            key="seleccion_incidencia_existente",
        )
        hallazgo = hallazgos[seleccionado]
        expediente = next(
            op for op in operaciones
            if op.identificador == hallazgo.identificador
        )
        if hallazgo.tipo == "DECLARACIÓN DE PAGO POR ACLARAR":
            mostrar_declaraciones_pendientes(expediente)
            st.caption(
                "El importe ya se encuentra fuera de los movimientos "
                "bancarios; requiere verificar el medio de pago por separado."
            )
        elif hallazgo.tipo == "REFERENCIA COMPARTIDA":
            st.warning(
                "Una referencia compartida requiere contrastar el voucher "
                "global y su distribución entre facturas. "
                "Todavía no se autoriza redistribuirla desde este editor."
            )
        else:
            mostrar_editor_incidencias(expediente, tipo=hallazgo.tipo)

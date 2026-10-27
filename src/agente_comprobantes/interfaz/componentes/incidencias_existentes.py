"""Diagnóstico de expedientes existentes, independiente del importador."""

import streamlit as st

from agente_comprobantes.control_financiero.auditoria_expedientes import (
    auditar_expedientes,
)
from agente_comprobantes.control_financiero.modelos import OperacionFlete


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
            "Busca el ID del expediente en la tabla de abajo para revisar "
            "sus comprobantes. Esta auditoría no registra ni acredita pagos."
        )

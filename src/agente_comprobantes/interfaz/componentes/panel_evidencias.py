"""Detalle de evidencia financiera, solo lectura."""

from __future__ import annotations

import streamlit as st

from agente_comprobantes.control_financiero.modelos import OperacionFlete
from agente_comprobantes.control_financiero.presentacion import formatear_importe


def mostrar_evidencias(operacion: OperacionFlete) -> None:
    registros: list[dict[str, str]] = []
    for banco in operacion.movimientos_bancarios:
        registros.append(
            {
                "Tipo": "Pago declarado",
                "Referencia": banco.referencia or "Pendiente",
                "Importe": formatear_importe(banco.importe_aplicado, banco.moneda),
                "Acreditación documental": "Sí" if banco.verificada else "No",
                "Archivo": banco.documento_respaldo or "Sin respaldo",
            }
        )
    for deposito in operacion.depositos_detraccion:
        registros.append(
            {
                "Tipo": "Detracción",
                "Referencia": deposito.referencia or "Pendiente",
                "Importe": formatear_importe(deposito.importe, deposito.moneda),
                "Acreditación documental": "Sí" if deposito.verificada else "No",
                "Archivo": deposito.documento_respaldo or "Sin respaldo",
            }
        )
    for nota in operacion.notas_credito:
        registros.append(
            {
                "Tipo": "Nota de crédito",
                "Referencia": nota.numero,
                "Importe": formatear_importe(nota.importe, nota.moneda),
                "Acreditación documental": "Sí" if nota.verificada else "No",
                "Archivo": nota.documento_respaldo or "Sin respaldo",
            }
        )
    if registros:
        st.dataframe(registros, hide_index=True, use_container_width=True)
    else:
        st.info("No se han asociado pagos, detracciones ni notas de crédito.")
    st.caption(
        "La acreditación es documental y declarada; no constituye "
        "una confirmación automática del banco o SUNAT."
    )

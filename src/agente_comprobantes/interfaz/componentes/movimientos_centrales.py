"""Prototipo seguro de movimientos centrales: solo borradores no acreditados."""

from __future__ import annotations

import streamlit as st

from agente_comprobantes.configuracion import Configuracion
from agente_comprobantes.control_financiero.modelos import OperacionFlete
from agente_comprobantes.control_financiero.repositorio_json import (
    RepositorioControlFletes,
)
from agente_comprobantes.control_financiero.repositorio_movimientos import (
    RepositorioMovimientosCentrales,
)
from agente_comprobantes.control_financiero.servicio_movimientos import (
    guardar_borrador_central,
)
from agente_comprobantes.dominio.enumeraciones import Moneda


def mostrar_movimientos_centrales(operaciones: list[OperacionFlete]) -> None:
    ruta_excel = Configuracion().ruta_archivo_excel()
    control = RepositorioControlFletes(
        ruta_excel.with_name("control_fletes.json")
    )
    registro = RepositorioMovimientosCentrales(
        ruta_excel.with_name("movimientos_bancarios_centrales.json")
    )
    with st.expander("Movimientos compartidos · borradores (piloto)"):
        st.caption(
            "Registra un voucher una sola vez y distribuye importes entre "
            "facturas. Esta sección es independiente de los pagos anteriores "
            "y NO afecta los saldos, acreditaciones o indicadores financieros."
        )
        try:
            existentes = registro.listar()
            huella_control = control.huella()
            huella_central = registro.huella()
        except (ValueError, OSError) as exc:
            st.error(f"No se pudo consultar el registro central: {exc}")
            return

        if existentes:
            st.dataframe(
                [
                    {
                        "ID": movimiento.identificador,
                        "Banco": movimiento.banco,
                        "Operación": movimiento.referencia,
                        "Moneda": movimiento.moneda.value,
                        "Importe total": str(movimiento.importe_total),
                        "Asignado": str(
                            movimiento.importe_total - movimiento.sin_asignar
                        ),
                        "Sin asignar": str(movimiento.sin_asignar),
                        "Facturas": ", ".join(
                            item.expediente for item in movimiento.aplicaciones
                        ),
                        "Estado": movimiento.estado,
                    }
                    for movimiento in existentes
                ],
                hide_index=True,
                use_container_width=True,
            )
            with st.expander("Consultar distribución de borradores"):
                seleccion = st.selectbox(
                    "Movimiento",
                    existentes,
                    format_func=lambda m: (
                        f"{m.referencia} · {m.banco} · {m.moneda.value}"
                    ),
                    key="movimiento_central_consulta",
                )
                st.dataframe(
                    [
                        {
                            "Expediente": item.expediente,
                            "Importe asignado": str(item.importe),
                            "Estado": "Declarado, no acreditado",
                        }
                        for item in seleccion.aplicaciones
                    ],
                    hide_index=True,
                    use_container_width=True,
                )
        monedas = sorted(
            {op.moneda for op in operaciones if op.moneda != Moneda.OTHER},
            key=lambda m: m.value,
        )
        moneda = st.selectbox(
            "Moneda del voucher", monedas, format_func=lambda m: m.value,
            key="moneda_central",
        )
        candidatas = [
            op for op in operaciones if op.moneda == moneda
        ]
        mapa = {op.identificador: op for op in candidatas}
        elegidos = st.multiselect(
            "Facturas a las que se distribuirá el voucher",
            list(mapa),
            format_func=lambda id_: (
                f"{mapa[id_].numero_factura} · {mapa[id_].proveedor or 'Sin proveedor'}"
            ),
            max_selections=10,
            key="facturas_voucher_central",
        )
        if not elegidos:
            st.info("Selecciona al menos una factura para preparar el borrador.")
        with st.form("formulario_movimiento_central"):
            banco = st.text_input("Entidad bancaria", placeholder="Ej. BCP")
            referencia = st.text_input(
                "Referencia individual del movimiento",
                placeholder="Ej. OP-0803971",
            )
            total = st.text_input(
                f"Importe total del voucher ({moneda.value})",
                placeholder="0.00",
            )
            importes = {
                id_: st.text_input(
                    f"Aplicar a {mapa[id_].numero_factura} ({moneda.value})",
                    placeholder="0.00",
                    key=f"aplicacion_central_{id_}",
                )
                for id_ in elegidos
            }
            sustento = st.text_area(
                "Sustento de la asignación",
                placeholder="Indica de qué documento procede el importe total.",
            )
            confirmar = st.checkbox(
                "Entiendo que se guardará solo un borrador, sin acreditación, "
                "y que no modificará los importes existentes."
            )
            enviado = st.form_submit_button(
                "Guardar borrador de movimiento",
                disabled=not elegidos,
            )
        if not enviado:
            return
        if not confirmar:
            st.error("Confirma el alcance del borrador antes de guardar.")
            return
        try:
            guardado = guardar_borrador_central(
                registro, control,
                banco=banco,
                referencia=referencia,
                moneda=moneda,
                importe_total=total,
                aplicaciones=list(importes.items()),
                sustento=sustento,
                huella_control=huella_control,
                huella_central=huella_central,
            )
        except (ValueError, OSError) as exc:
            st.error(f"No se guardó el borrador: {exc}")
            return
        st.session_state["_mensaje_revision"] = (
            f"Movimiento {guardado.identificador} registrado como BORRADOR. "
            "Ningún saldo financiero ha cambiado."
        )
        st.rerun()

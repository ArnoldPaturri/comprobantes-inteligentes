"""Prototipo seguro de movimientos centrales: solo borradores no acreditados."""

from __future__ import annotations

import streamlit as st

from agente_comprobantes.configuracion import Configuracion
from agente_comprobantes.control_financiero.archivos import almacen_para_excel
from agente_comprobantes.control_financiero.modelos import OperacionFlete
from agente_comprobantes.control_financiero.movimientos_centrales import (
    MovimientoBancarioCentral,
)
from agente_comprobantes.control_financiero.repositorio_json import (
    RepositorioControlFletes,
)
from agente_comprobantes.control_financiero.repositorio_movimientos import (
    RepositorioMovimientosCentrales,
)
from agente_comprobantes.control_financiero.servicio_movimientos import (
    adjuntar_voucher_central,
    documentar_movimiento_central,
    guardar_borrador_central,
    redistribuir_movimiento_central,
    reabrir_movimiento_central,
)
from agente_comprobantes.dominio.enumeraciones import Moneda
from agente_comprobantes.interfaz.componentes.visor_adjuntos import mostrar_respaldo


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
        if existentes:
            _gestionar_existentes(
                existentes, operaciones, registro, control,
                huella_central=huella_central, huella_control=huella_control,
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


def _gestionar_existentes(
    movimientos: list[MovimientoBancarioCentral],
    operaciones: list[OperacionFlete],
    registro: RepositorioMovimientosCentrales,
    control: RepositorioControlFletes,
    *,
    huella_central: str,
    huella_control: str,
) -> None:
    """Editar una distribución y revisar su voucher sin generar pagos duplicados."""
    with st.expander("Gestionar movimiento existente · distribución y voucher"):
        elegido = st.selectbox(
            "Movimiento registrado",
            movimientos,
            format_func=lambda m: (
                f"{m.referencia} · {m.moneda.value} · {m.estado}"
            ),
            key="central_movimiento_gestion",
        )
        st.caption(
            f"Total: {elegido.importe_total} · "
            f"Distribuido: {elegido.importe_total - elegido.sin_asignar} · "
            f"Sin asignar: {elegido.sin_asignar}"
        )
        mostrar_respaldo(elegido.respaldo, clave=f"central_{elegido.identificador}")
        if elegido.revisiones:
            with st.expander(f"Historial de revisiones ({len(elegido.revisiones)})"):
                for revision in reversed(elegido.revisiones):
                    st.write(revision.fecha.strftime("%Y-%m-%d %H:%M UTC"))
                    st.caption(f"{revision.accion}: {revision.motivo}")
                    st.json(revision.cambios)

        st.markdown("**Distribución entre facturas**")
        if elegido.estado == "BORRADOR":
            candidatas = {
                op.identificador: op
                for op in operaciones if op.moneda == elegido.moneda
            }
            seleccion = st.multiselect(
                "Facturas de la misma moneda",
                list(candidatas),
                default=[
                    a.expediente for a in elegido.aplicaciones
                    if a.expediente in candidatas
                ],
                format_func=lambda codigo: (
                    f"{candidatas[codigo].numero_factura} · "
                    f"{candidatas[codigo].proveedor or 'Sin proveedor'}"
                ),
                key=f"central_editar_facturas_{elegido.identificador}",
            )
            existentes = {
                a.expediente: a.importe for a in elegido.aplicaciones
            }
            with st.form(f"redistribuir_{elegido.identificador}"):
                importes = [
                    (
                        identificador,
                        st.text_input(
                            f"Importe para {candidatas[identificador].numero_factura}",
                            value=str(existentes.get(identificador, "")),
                            key=f"central_editar_importe_{elegido.identificador}_{identificador}",
                        ),
                    )
                    for identificador in seleccion
                ]
                motivo = st.text_area("Motivo de la redistribución")
                confirmar = st.checkbox(
                    "Confirmo los importes y que aún no son pagos acreditados."
                )
                enviado = st.form_submit_button(
                    "Guardar nueva distribución", disabled=not seleccion
                )
            if enviado:
                try:
                    redistribuir_movimiento_central(
                        registro, control, elegido.identificador,
                        aplicaciones=importes, motivo=motivo, confirmacion=confirmar,
                        huella_central=huella_central, huella_control=huella_control,
                    )
                except (ValueError, OSError) as exc:
                    st.error(str(exc))
                else:
                    st.session_state["_mensaje_revision"] = (
                        "Distribución corregida; ningún pago fue acreditado."
                    )
                    st.rerun()
        else:
            st.info(
                "Movimiento ya documentado. La distribución no puede editarse "
                "sin un proceso explícito de reversión."
            )

        st.markdown("**Vinculación del voucher central**")
        with st.form(f"adjuntar_central_{elegido.identificador}"):
            archivo = st.file_uploader(
                "Voucher bancario (PDF, PNG o JPG)",
                type=["pdf", "png", "jpg", "jpeg"],
                key=f"central_archivo_{elegido.identificador}",
            )
            motivo_archivo = st.text_area("Motivo de la vinculación o reemplazo")
            confirma_archivo = st.checkbox(
                "Confirmo que el archivo corresponde a este movimiento."
            )
            guardar_archivo = st.form_submit_button("Guardar voucher")
        if guardar_archivo:
            if archivo is None:
                st.error("Selecciona un archivo válido.")
            else:
                try:
                    adjuntar_voucher_central(
                        registro, control,
                        almacen_para_excel(Configuracion().ruta_archivo_excel()),
                        elegido.identificador,
                        nombre=archivo.name,
                        contenido=archivo.getvalue(),
                        motivo=motivo_archivo,
                        confirmacion=confirma_archivo,
                        huella_central=huella_central, huella_control=huella_control,
                    )
                except (ValueError, OSError) as exc:
                    st.error(str(exc))
                else:
                    st.session_state["_mensaje_revision"] = (
                        "Voucher central vinculado; falta revisión documental."
                    )
                    st.rerun()

        if elegido.estado == "BORRADOR":
            st.markdown("**Revisión documental del movimiento**")
            st.caption(
                "DOCUMENTADO significa cotejo humano del voucher y la distribución. "
                "No implica confirmación bancaria ni modifica los saldos oficiales."
            )
            with st.form(f"documentar_central_{elegido.identificador}"):
                motivo_revision = st.text_area("Resultado y sustento del cotejo")
                confirma_revision = st.checkbox(
                    "He examinado el voucher original y contrastado banco, "
                    "referencia, importe, moneda y aplicaciones."
                )
                revisar = st.form_submit_button(
                    "Marcar como documentado", disabled=not elegido.respaldo
                )
            if revisar:
                try:
                    documentar_movimiento_central(
                        registro, control,
                        almacen_para_excel(Configuracion().ruta_archivo_excel()),
                        elegido.identificador,
                        motivo=motivo_revision, confirmacion=confirma_revision,
                        huella_central=huella_central, huella_control=huella_control,
                    )
                except (ValueError, OSError) as exc:
                    st.error(str(exc))
                else:
                    st.session_state["_mensaje_revision"] = (
                        "Movimiento documentado. No se alteraron los saldos oficiales."
                    )
                    st.rerun()

        if elegido.estado == "DOCUMENTADO":
            with st.form(f"reabrir_central_{elegido.identificador}"):
                motivo_reapertura = st.text_area("Motivo de la reapertura")
                confirmar_reapertura = st.checkbox(
                    "Confirmo la revocación de la revisión documental. "
                    "Se conservará el voucher y el historial."
                )
                reapertura = st.form_submit_button("Reabrir para correcciones")
            if reapertura:
                try:
                    reabrir_movimiento_central(
                        registro, control, elegido.identificador,
                        motivo=motivo_reapertura,
                        confirmacion=confirmar_reapertura,
                        huella_central=huella_central,
                        huella_control=huella_control,
                    )
                except (ValueError, OSError) as exc:
                    st.error(str(exc))
                else:
                    st.session_state["_mensaje_revision"] = (
                        "Revisión revocada. Movimiento nuevamente en borrador."
                    )
                    st.rerun()

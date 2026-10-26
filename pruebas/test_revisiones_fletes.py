"""Revisión humana: clasificación, persistencia e historial mínimo."""

from decimal import Decimal

import pytest

from agente_comprobantes.control_financiero.conciliacion import conciliar_flete
from agente_comprobantes.control_financiero.modelos import OperacionFlete, SituacionControl
from agente_comprobantes.control_financiero.presentacion import construir_tablero
from agente_comprobantes.control_financiero.repositorio_json import RepositorioControlFletes
from agente_comprobantes.control_financiero.revisiones import (
    guardar_revision,
    preparar_revision,
)
from agente_comprobantes.dominio.enumeraciones import Moneda


def operacion() -> OperacionFlete:
    return OperacionFlete(
        identificador="FAC-MATERIALES",
        numero_factura="F001-201",
        moneda=Moneda.PEN,
        monto_facturado=Decimal("1000"),
        monto_cotizado=Decimal("900"),
        codigo_cotizacion="COT-11",
        proveedor="Materiales Andinos",
    )


def test_borrador_sin_clasificar_no_contamina_indicadores_de_fletes() -> None:
    op = operacion()
    tablero = construir_tablero([op])
    assert len(tablero.operaciones) == 1
    assert tablero.resumenes == []
    assert tablero.filas()[0].clasificacion == "Sin clasificar"
    assert conciliar_flete(op).situacion == SituacionControl.PENDIENTE


def test_materiales_excluidos_no_se_convierten_en_fletes() -> None:
    op = preparar_revision(
        operacion(), es_flete=False, numero_guia=None, detraccion_aplica=None,
        motivo="Factura de compra de materiales", confirmacion=True,
    )
    assert construir_tablero([op]).resumenes == []
    assert conciliar_flete(op).situacion == SituacionControl.PENDIENTE


def test_confirmar_flete_habilita_presupuesto_en_panel() -> None:
    op = preparar_revision(
        operacion(), es_flete=True, numero_guia="EG-001", detraccion_aplica=None,
        motivo="Servicio de transporte revisado", confirmacion=True,
    )
    tablero = construir_tablero([op])
    assert tablero.resumenes[0].total_presupuestado == 900
    assert tablero.filas()[0].guia == "EG-001"
    assert op.revisiones[0].cambios["es_flete"] == "None → True"
    assert not op.conciliacion_cerrada


@pytest.mark.parametrize(
    ("motivo", "confirmado"),
    [("Muy corto", True), ("Revisión con documentos", False)],
)
def test_no_guardar_sin_motivo_o_confirmacion(motivo: str, confirmado: bool) -> None:
    with pytest.raises(ValueError):
        preparar_revision(
            operacion(), es_flete=True, numero_guia=None,
            detraccion_aplica=None, motivo=motivo, confirmacion=confirmado,
        )


def test_no_calcular_detraccion_a_materiales() -> None:
    with pytest.raises(ValueError, match="Solo se clasifica"):
        preparar_revision(
            operacion(), es_flete=False, numero_guia=None,
            detraccion_aplica=False, motivo="No corresponde al transporte",
            confirmacion=True,
        )


def test_revision_guarda_json_sin_modificar_importes(tmp_path) -> None:
    ruta = tmp_path / "control_fletes.json"
    repo = RepositorioControlFletes(ruta)
    repo.agregar(operacion())
    actualizado = guardar_revision(
        repo, "FAC-MATERIALES", es_flete=True, numero_guia="EG-99",
        detraccion_aplica=None, motivo="Factura de flete documentada",
        confirmacion=True,
    )
    assert actualizado.numero_guia == "EG-99"
    assert actualizado.monto_facturado == Decimal("1000")
    cargado = repo.obtener("FAC-MATERIALES")
    assert len(cargado.revisiones) == 1
    assert cargado.revisiones[0].motivo == "Factura de flete documentada"
    with pytest.raises(ValueError, match="No hay cambios"):
        guardar_revision(
            repo, "FAC-MATERIALES", es_flete=True, numero_guia="EG-99",
            detraccion_aplica=None, motivo="Se revisó nuevamente", confirmacion=True,
        )
    assert len(repo.obtener("FAC-MATERIALES").revisiones) == 1

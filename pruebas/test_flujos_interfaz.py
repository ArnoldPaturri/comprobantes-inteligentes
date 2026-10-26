"""Pruebas de estado para los flujos de revisión de Streamlit."""

from importlib import import_module

import pytest


@pytest.mark.parametrize(
    ("modulo", "nombres_claves"),
    [
        (
            "agente_comprobantes.interfaz.flujos.factura",
            ("_PREVIEW_KEY", "_PATHS_KEY", "_QUOTATION_KEY", "_ELAPSED_KEY"),
        ),
        (
            "agente_comprobantes.interfaz.flujos.pago",
            ("_PREVIEW_KEY", "_PATHS_KEY", "_QUOTATION_KEY", "_INVOICE_KEY", "_MODE_KEY"),
        ),
    ],
)
def test_limpiar_previsualizacion_conserva_resultado(
    monkeypatch: pytest.MonkeyPatch,
    modulo: str,
    nombres_claves: tuple[str, ...],
) -> None:
    flujo = import_module(modulo)
    clave_resultado = getattr(flujo, "_RESULT_KEY")
    sesion = {getattr(flujo, nombre): "temporal" for nombre in nombres_claves}
    sesion[clave_resultado] = {"document_id": "REG-001"}

    monkeypatch.setattr(flujo.st, "session_state", sesion)

    flujo.limpiar_previsualizacion()

    assert sesion == {clave_resultado: {"document_id": "REG-001"}}

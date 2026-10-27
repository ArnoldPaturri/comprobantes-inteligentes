"""Revisión de pagos: evidencias, trazabilidad y no alteración del Excel."""

from decimal import Decimal

import pytest

from agente_comprobantes.control_financiero.conciliacion import conciliar_flete
from agente_comprobantes.control_financiero.modelos import (
    MovimientoBancario,
    OperacionFlete,
    SituacionControl,
)
from agente_comprobantes.control_financiero.repositorio_json import (
    RepositorioControlFletes,
)
from agente_comprobantes.control_financiero.revision_pagos import (
    guardar_revision_pago,
    preparar_revision_pago,
)
from agente_comprobantes.dominio.enumeraciones import Moneda


def operacion(**cambios: object) -> OperacionFlete:
    datos = {
        "identificador": "FAC-01",
        "numero_factura": "F001-21",
        "moneda": Moneda.PEN,
        "monto_facturado": Decimal("1000"),
        "es_flete": True,
        "numero_guia": "EG-100",
        "evidencia_factura": "factura.pdf",
        "detraccion_aplica": False,
        "movimientos_bancarios": [
            MovimientoBancario(
                importe_aplicado=Decimal("1000"),
                moneda=Moneda.PEN,
                referencia="OP-123",
                documento_respaldo="adjunto:" + "a" * 64 + ".pdf",
                verificada=False,
            )
        ],
        "conciliacion_cerrada": False,
    }
    datos.update(cambios)
    return OperacionFlete(**datos)


def revisar(op: OperacionFlete, **cambios: object) -> OperacionFlete:
    datos = {
        "indice": 0,
        "acreditar": True,
        "motivo": "Comprobante y operación cotejados manualmente",
        "confirmacion": True,
        "version_esperada": len(op.revisiones),
    }
    datos.update(cambios)
    return preparar_revision_pago(op, **datos)


def test_aprobacion_manual_separa_estado_de_conciliacion() -> None:
    antes = operacion()
    despues = revisar(antes)
    assert not antes.movimientos_bancarios[0].verificada
    assert despues.movimientos_bancarios[0].verificada
    assert conciliar_flete(despues).bancarizado_acreditado == Decimal("1000")
    assert conciliar_flete(despues).situacion == SituacionControl.PENDIENTE
    assert not despues.conciliacion_cerrada
    assert len(despues.revisiones) == 1
    assert despues.revisiones[0].motivo.startswith("Comprobante")
    assert "movimientos_bancarios[0].verificada" in despues.revisiones[0].cambios


def test_revocar_acreditacion_resta_importe_e_historial() -> None:
    acreditada = revisar(operacion())
    revocada = revisar(
        acreditada,
        acreditar=False,
        motivo="Comprobante observado y acreditación retirada",
    )
    assert conciliar_flete(revocada).bancarizado_acreditado == Decimal("0")
    assert len(revocada.revisiones) == 2
    assert not revocada.movimientos_bancarios[0].verificada


@pytest.mark.parametrize(
    ("atributo", "valor", "mensaje"),
    [
        ("referencia", None, "número de operación"),
        ("referencia", "  ", "número de operación"),
        ("documento_respaldo", None, "comprobante original"),
        ("moneda", Moneda.USD, "moneda"),
    ],
)
def test_no_acreditar_evidencia_incompleta(
    atributo: str, valor: object, mensaje: str
) -> None:
    original = operacion()
    movimiento = original.movimientos_bancarios[0].model_copy(update={atributo: valor})
    op = original.model_copy(update={"movimientos_bancarios": [movimiento]})
    with pytest.raises(ValueError, match=mensaje):
        revisar(op)


@pytest.mark.parametrize(
    "cambios",
    [
        {"motivo": "Corto"},
        {"confirmacion": False},
        {"indice": -1},
        {"indice": 7},
        {"version_esperada": 99},
    ],
)
def test_datos_de_revision_invalidos(cambios: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        revisar(operacion(), **cambios)


def test_no_duplicar_acreditacion() -> None:
    with pytest.raises(ValueError, match="ya está registrada"):
        revisar(revisar(operacion()))


def test_guardar_revision_json_no_modifica_excel(tmp_path) -> None:
    libro = tmp_path / "registros.xlsx"
    libro.write_bytes(b"contenido de prueba")
    ruta = tmp_path / "control_fletes.json"
    repo = RepositorioControlFletes(ruta)
    repo.agregar(operacion())
    actualizada = guardar_revision_pago(
        repo,
        "FAC-01",
        indice=0,
        acreditar=True,
        motivo="Validación documental de la operación OP-123",
        confirmacion=True,
        version_esperada=0,
    )
    assert actualizada.movimientos_bancarios[0].verificada
    assert repo.obtener("FAC-01").revisiones[0].cambios["referencia"] == "OP-123"
    assert libro.read_bytes() == b"contenido de prueba"
    original_json = ruta.read_bytes()
    with pytest.raises(ValueError, match="cambió"):
        guardar_revision_pago(
            repo,
            "FAC-01",
            indice=0,
            acreditar=False,
            motivo="Confirmar la reversión de esta operación",
            confirmacion=True,
            version_esperada=0,
        )
    assert ruta.read_bytes() == original_json


def test_no_acreditar_efectivo_aunque_tenga_adjunto() -> None:
    documento = operacion()
    pago = documento.movimientos_bancarios[0].model_copy(
        update={"referencia": "EFECTIVO?"}
    )
    documento = documento.model_copy(update={"movimientos_bancarios": [pago]})
    with pytest.raises(ValueError, match="EFECTIVO"):
        revisar(documento)


def test_no_acreditar_referencia_compuesta_aunque_tenga_adjunto() -> None:
    documento = operacion()
    pago = documento.movimientos_bancarios[0].model_copy(
        update={"referencia": "6537194 Y 340464"}
    )
    documento = documento.model_copy(update={"movimientos_bancarios": [pago]})
    with pytest.raises(ValueError, match="desglosa"):
        revisar(documento)


def test_no_acreditar_voucher_nominal_sin_adjunto_interno() -> None:
    documento = operacion()
    pago = documento.movimientos_bancarios[0].model_copy(
        update={"documento_respaldo": "voucher.pdf"}
    )
    documento = documento.model_copy(update={"movimientos_bancarios": [pago]})
    with pytest.raises(ValueError, match="Adjunta"):
        revisar(documento)


def test_bloquear_referencia_compartida_en_dos_expedientes(tmp_path) -> None:
    repo = RepositorioControlFletes(tmp_path / "control_fletes.json")
    primera = operacion()
    datos_segunda = operacion().model_dump(mode="python")
    datos_segunda["identificador"] = "FAC-02"
    datos_segunda["numero_factura"] = "F001-22"
    segunda = OperacionFlete.model_validate(datos_segunda)
    repo.agregar(primera)
    repo.agregar(segunda)
    anterior = (tmp_path / "control_fletes.json").read_bytes()
    with pytest.raises(ValueError, match="otro movimiento"):
        guardar_revision_pago(
            repo, "FAC-01", indice=0, acreditar=True,
            motivo="Vouchers revisados manualmente por el responsable",
            confirmacion=True, version_esperada=0,
        )
    assert (tmp_path / "control_fletes.json").read_bytes() == anterior


def test_no_acreditar_referencia_repetida_en_una_factura() -> None:
    original = operacion()
    repetido = original.movimientos_bancarios[0].model_copy(deep=True)
    duplicada = original.model_copy(
        update={"movimientos_bancarios": [
            original.movimientos_bancarios[0], repetido
        ]}
    )
    with pytest.raises(ValueError, match="otro movimiento"):
        preparar_revision_pago(
            duplicada, indice=0, acreditar=True,
            motivo="El pago fue comparado con los documentos",
            confirmacion=True, version_esperada=0,
        )


def test_se_puede_revocar_aun_si_la_referencia_se_volvio_ambigua() -> None:
    acreditada = revisar(operacion())
    pago = acreditada.movimientos_bancarios[0].model_copy(
        update={"referencia": "EFECTIVO?"}
    )
    acreditada = acreditada.model_copy(
        update={"movimientos_bancarios": [pago]}
    )
    revocada = preparar_revision_pago(
        acreditada, indice=0, acreditar=False,
        motivo="Se revoca por inconsistencias de la referencia original",
        confirmacion=True, version_esperada=1,
    )
    assert not revocada.movimientos_bancarios[0].verificada

"""Pruebas de registro y revisión de detracciones y notas de crédito."""

from decimal import Decimal

import pytest

from agente_comprobantes.control_financiero.conciliacion import conciliar_flete
from agente_comprobantes.control_financiero.modelos import (
    MovimientoBancario,
    OperacionFlete,
)
from agente_comprobantes.control_financiero.registro_ajustes import (
    guardar_registro_evidencia,
    guardar_revision_evidencia,
    preparar_registro_evidencia,
    preparar_revision_evidencia,
)
from agente_comprobantes.control_financiero.repositorio_json import (
    RepositorioControlFletes,
)
from agente_comprobantes.dominio.enumeraciones import Moneda


def operacion(**kwargs: object) -> OperacionFlete:
    base = {
        "identificador": "FAC-TEST",
        "numero_factura": "F001-100",
        "moneda": Moneda.PEN,
        "monto_facturado": "1000",
        "numero_guia": "EG-2",
        "es_flete": True,
        "detraccion_aplica": True,
        "evidencia_factura": "factura.pdf",
        "movimientos_bancarios": [
            MovimientoBancario(
                moneda=Moneda.PEN,
                importe_aplicado="940",
                referencia="OP-12",
                documento_respaldo="pago.pdf",
                verificada=True,
            )
        ],
    }
    base.update(kwargs)
    return OperacionFlete(**base)


def registrar(op: OperacionFlete, tipo: str, **kwargs: object) -> OperacionFlete:
    data = {
        "tipo": tipo,
        "referencia": "SPOT-20" if tipo == "detraccion" else "NC-20",
        "respaldo": "constancia.pdf",
        "monto": "60.00" if tipo == "detraccion" else "100.00",
        "numero": "FC01-20" if tipo == "nota_credito" else None,
        "motivo": "Revisé documento de prueba y referencias",
        "confirmacion": True,
        "version_esperada": len(op.revisiones),
    }
    data.update(kwargs)
    return preparar_registro_evidencia(op, **data)


def revisar(op: OperacionFlete, tipo: str, **kwargs: object) -> OperacionFlete:
    data = {
        "tipo": tipo,
        "indice": 0,
        "acreditar": True,
        "motivo": "Revisé la constancia junto a la factura",
        "confirmacion": True,
        "version_esperada": len(op.revisiones),
    }
    data.update(kwargs)
    return preparar_revision_evidencia(op, **data)


def test_deposito_inicia_no_acreditado_y_luego_concilia() -> None:
    inicial = operacion()
    registrado = registrar(inicial, "detraccion")
    assert not registrado.depositos_detraccion[0].verificada
    assert conciliar_flete(registrado).detraccion_acreditada == 0
    final = revisar(registrado, "detraccion")
    assert conciliar_flete(final).detraccion_acreditada == Decimal("60.00")
    assert conciliar_flete(final).saldo_por_acreditar == Decimal("0")
    assert not final.conciliacion_cerrada
    assert len(final.revisiones) == 2


def test_nota_credito_no_descontada_hasta_revision() -> None:
    op = operacion(movimientos_bancarios=[])
    registrada = registrar(op, "nota_credito")
    assert conciliar_flete(registrada).facturado_neto == Decimal("1000")
    acreditada = revisar(registrada, "nota_credito")
    assert conciliar_flete(acreditada).facturado_neto == Decimal("900")
    assert acreditada.notas_credito[0].numero == "FC01-20"


def test_retirar_acreditacion_recupera_base_original() -> None:
    nota = revisar(registrar(operacion(), "nota_credito"), "nota_credito")
    revocada = revisar(
        nota,
        "nota_credito",
        acreditar=False,
        motivo="La constancia resultó incorrecta en revisión",
    )
    assert conciliar_flete(revocada).facturado_neto == 1000
    assert len(revocada.revisiones) == 3


@pytest.mark.parametrize(
    "cambio",
    [
        {"monto": "0"},
        {"monto": "-10"},
        {"monto": "12.345"},
        {"monto": "NaN"},
        {"monto": "1e200"},
        {"referencia": ""},
        {"respaldo": " "},
        {"confirmacion": False},
        {"motivo": "breve"},
        {"version_esperada": 99},
    ],
)
def test_validacion_rechaza_registros_incorrectos(cambio: dict) -> None:
    with pytest.raises((ValueError, OverflowError)):
        registrar(operacion(), "detraccion", **cambio)


@pytest.mark.parametrize(
    "cambio",
    [
        {"es_flete": False},
        {"es_flete": None},
        {"detraccion_aplica": False},
        {"detraccion_aplica": None},
    ],
)
def test_no_registrar_detraccion_sin_confirmacion_de_actividad(cambio: dict) -> None:
    with pytest.raises(ValueError, match="confirma que es un flete"):
        registrar(operacion(**cambio), "detraccion")


def test_importe_de_detraccion_mayor_a_factura_es_invalido() -> None:
    with pytest.raises(ValueError, match="superar"):
        registrar(operacion(), "detraccion", monto="1000.01")


def test_numero_nc_unico_y_limite_por_factura() -> None:
    op = registrar(operacion(), "nota_credito")
    with pytest.raises(ValueError, match="Ya existe"):
        registrar(op, "nota_credito", numero="fc01-20")
    with pytest.raises(ValueError, match="supera la factura"):
        registrar(op, "nota_credito", numero="FC01-21", monto="901")


def test_referencia_deposito_no_duplicada() -> None:
    op = registrar(operacion(), "detraccion")
    with pytest.raises(ValueError, match="Ya existe"):
        registrar(op, "detraccion", referencia="spot-20")


def test_no_puede_acreditar_documento_sin_evidencia(tmp_path) -> None:
    op = registrar(operacion(), "detraccion")
    alterado = op.depositos_detraccion[0].model_copy(
        update={"documento_respaldo": None}
    )
    op = op.model_copy(update={"depositos_detraccion": [alterado]})
    with pytest.raises(ValueError, match="respaldo"):
        revisar(op, "detraccion")


def test_indices_validos_y_estado_de_revision() -> None:
    op = registrar(operacion(), "nota_credito")
    with pytest.raises(ValueError, match="cambió"):
        revisar(op, "nota_credito", version_esperada=0)
    with pytest.raises(ValueError, match="no existe"):
        revisar(op, "nota_credito", indice=10)
    with pytest.raises(ValueError, match="ya estaba"):
        revisar(revisar(op, "nota_credito"), "nota_credito")


def test_persistencia_independiente_no_toca_excel(tmp_path) -> None:
    excel = tmp_path / "registros.xlsx"
    excel.write_bytes(b"excel-prueba")
    repo = RepositorioControlFletes(tmp_path / "control_fletes.json")
    repo.agregar(operacion())
    registro = guardar_registro_evidencia(
        repo,
        "FAC-TEST",
        tipo="detraccion",
        referencia="SPOT-100",
        respaldo="constancia100.pdf",
        monto="60",
        motivo="Deposito ingresado para revision documental",
        confirmacion=True,
        version_esperada=0,
    )
    assert not registro.depositos_detraccion[0].verificada
    guardada = guardar_revision_evidencia(
        repo,
        "FAC-TEST",
        tipo="detraccion",
        indice=0,
        acreditar=True,
        motivo="Constancia y referencia cotejadas manualmente",
        confirmacion=True,
        version_esperada=1,
    )
    assert guardada.depositos_detraccion[0].verificada
    assert repo.obtener("FAC-TEST") == guardada
    assert excel.read_bytes() == b"excel-prueba"
    original_bytes = (tmp_path / "control_fletes.json").read_bytes()
    with pytest.raises(ValueError, match="cambió"):
        guardar_revision_evidencia(
            repo,
            "FAC-TEST",
            tipo="detraccion",
            indice=0,
            acreditar=False,
            motivo="Correccion realizada sobre documento",
            confirmacion=True,
            version_esperada=0,
        )
    assert (tmp_path / "control_fletes.json").read_bytes() == original_bytes

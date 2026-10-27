"""Pruebas del registro central; no modifica saldos ni conciliación previa."""

from decimal import Decimal

import pytest

from agente_comprobantes.control_financiero.conciliacion import conciliar_flete
from agente_comprobantes.control_financiero.modelos import (
    MovimientoBancario,
    OperacionFlete,
)
from agente_comprobantes.control_financiero.movimientos_centrales import (
    AplicacionBancaria,
    MovimientoBancarioCentral,
)
from agente_comprobantes.control_financiero.repositorio_json import (
    RepositorioControlFletes,
)
from agente_comprobantes.control_financiero.repositorio_movimientos import (
    RepositorioMovimientosCentrales,
)
from agente_comprobantes.control_financiero.servicio_movimientos import (
    guardar_borrador_central,
    preparar_borrador_central,
)
from agente_comprobantes.dominio.enumeraciones import Moneda


def factura(
    codigo: str,
    moneda: Moneda = Moneda.PEN,
    pagos: list[MovimientoBancario] | None = None,
) -> OperacionFlete:
    return OperacionFlete(
        identificador=codigo,
        numero_factura=codigo.replace("FAC", "F001"),
        moneda=moneda,
        monto_facturado=Decimal("1000"),
        proveedor="Transportes Sur",
        movimientos_bancarios=pagos or [],
    )


def borrador(
    facturas: list[OperacionFlete],
    **opciones,
) -> MovimientoBancarioCentral:
    datos = {
        "banco": "BCP",
        "referencia": "OP-0803971",
        "moneda": Moneda.PEN,
        "importe_total": "1000.00",
        "aplicaciones": [("FAC-1", "400.00"), ("FAC-2", "600.00")],
        "sustento": "Vouchers individuales comparados para control",
        "facturas": facturas,
        "previos": [],
    }
    datos.update(opciones)
    return preparar_borrador_central(**datos)


def test_voucher_unico_se_distribuye_sin_duplicar() -> None:
    creado = borrador([factura("FAC-1"), factura("FAC-2")])
    assert creado.estado == "BORRADOR"
    assert creado.importe_total == Decimal("1000")
    assert creado.sin_asignar == Decimal("0")
    assert len(creado.aplicaciones) == 2
    assert creado.aplicaciones[0].importe == Decimal("400")
    assert creado.aplicaciones[1].importe == Decimal("600")


def test_importe_parcial_deja_saldo_no_asignado() -> None:
    creado = borrador(
        [factura("FAC-1")],
        aplicaciones=[("FAC-1", "400")],
    )
    assert creado.sin_asignar == Decimal("600")


@pytest.mark.parametrize(
    ("aplicaciones", "error"),
    [
        ([("FAC-1", "650"), ("FAC-2", "500")], "supera"),
        ([("FAC-1", "400"), ("FAC-1", "600")], "dos aplicaciones"),
        ([("FAC-1", "0")], "mayor que cero"),
        ([("FAC-1", "-20")], "no negativo"),
        ([("FAC-1", "1.001")], "dos decimales"),
        ([], "al menos una"),
    ],
)
def test_prohibir_aplicaciones_invalidas(aplicaciones, error) -> None:
    with pytest.raises(ValueError, match=error):
        borrador(
            [factura("FAC-1"), factura("FAC-2")],
            aplicaciones=aplicaciones,
        )


def test_no_acepta_moneda_diferente_entre_pago_y_factura() -> None:
    with pytest.raises(ValueError, match="misma moneda"):
        borrador([
            factura("FAC-1"),
            factura("FAC-2", Moneda.USD),
        ])


def test_no_acepta_efectivo_ni_ref_compuesta() -> None:
    for ref in ("EFECTIVO?", "111 Y 222"):
        with pytest.raises(ValueError, match="referencia bancaria individual"):
            borrador([factura("FAC-1")], referencia=ref,
                    aplicaciones=[("FAC-1", "500")])


def test_no_acepta_movimiento_historico_de_la_misma_referencia() -> None:
    movimiento = MovimientoBancario(
        moneda=Moneda.PEN,
        importe_aplicado=Decimal("200"),
        referencia="OP-0803971",
    )
    with pytest.raises(ValueError, match="histórico"):
        borrador(
            [factura("FAC-1", pagos=[movimiento]), factura("FAC-2")],
        )


def test_no_acepta_pagos_históricos_mas_nuevos_superiores_a_factura() -> None:
    pago_previo = MovimientoBancario(
        moneda=Moneda.PEN,
        importe_aplicado=Decimal("800"),
        referencia="OP-ANTERIOR",
    )
    with pytest.raises(ValueError, match="excede"):
        borrador(
            [factura("FAC-1", pagos=[pago_previo]), factura("FAC-2")],
        )


def test_no_acepta_ref_ya_existente_en_borradores() -> None:
    primero = borrador([factura("FAC-1"), factura("FAC-2")])
    with pytest.raises(ValueError, match="registro central"):
        borrador([factura("FAC-1"), factura("FAC-2")], previos=[primero])


def test_rechaza_expediente_desconocido() -> None:
    with pytest.raises(ValueError, match="No existe"):
        borrador(
            [factura("FAC-1")],
            aplicaciones=[("FAC-NO-EXISTE", "100")],
        )


def test_guardar_no_modifica_saldos_ni_archivo_excel(tmp_path) -> None:
    archivo_excel = tmp_path / "registros.xlsx"
    archivo_excel.write_bytes(b"archivo-operativo")
    control = RepositorioControlFletes(tmp_path / "control_fletes.json")
    central = RepositorioMovimientosCentrales(
        tmp_path / "movimientos_bancarios_centrales.json"
    )
    control.agregar(factura("FAC-1"))
    control.agregar(factura("FAC-2"))
    json_previo = (tmp_path / "control_fletes.json").read_bytes()
    saldo_previo = conciliar_flete(control.obtener("FAC-1")).saldo_por_acreditar
    creado = guardar_borrador_central(
        central,
        control,
        banco="BCP",
        referencia="OP-0803971",
        moneda=Moneda.PEN,
        importe_total="1000",
        aplicaciones=[("FAC-1", "400"), ("FAC-2", "600")],
        sustento="Distribución para conciliación documental futura",
        huella_control=control.huella(),
        huella_central=central.huella(),
    )
    almacenado = central.listar()[0]
    assert almacenado.model_dump(mode="json") == creado.model_dump(mode="json")
    assert almacenado.estado == "BORRADOR"
    assert archivo_excel.read_bytes() == b"archivo-operativo"
    assert (tmp_path / "control_fletes.json").read_bytes() == json_previo
    assert conciliar_flete(control.obtener("FAC-1")).saldo_por_acreditar == saldo_previo


def test_segundo_voucher_sobre_misma_factura_respeta_otros_borradores() -> None:
    primero = borrador(
        [factura("FAC-1")],
        aplicaciones=[("FAC-1", "700")],
    )
    with pytest.raises(ValueError, match="excede"):
        borrador(
            [factura("FAC-1")],
            referencia="OP-OTRA",
            aplicaciones=[("FAC-1", "400")],
            previos=[primero],
        )


def test_control_modificado_bloquea_borrador(tmp_path) -> None:
    control = RepositorioControlFletes(tmp_path / "control.json")
    central = RepositorioMovimientosCentrales(tmp_path / "central.json")
    control.agregar(factura("FAC-1"))
    anterior = control.huella()
    control.agregar(factura("FAC-2"))
    with pytest.raises(ValueError, match="cambiaron"):
        guardar_borrador_central(
            central, control, banco="BCP", referencia="OP-0803971",
            moneda=Moneda.PEN, importe_total="100",
            aplicaciones=[("FAC-1", "100")],
            sustento="Revisión del importe previo a guardar",
            huella_control=anterior,
            huella_central=central.huella(),
        )
    assert not central.ruta.exists()


def test_repo_central_rechaza_referencia_duplicada_y_borrador_obsoleto(
    tmp_path,
) -> None:
    repo = RepositorioMovimientosCentrales(tmp_path / "central.json")
    op = borrador([factura("FAC-1"), factura("FAC-2")])
    viejo = repo.huella()
    repo.agregar(op, huella_esperada=viejo)
    with pytest.raises(ValueError, match="cambió"):
        repo.agregar(op, huella_esperada=viejo)
    copia = MovimientoBancarioCentral.model_validate(
        {**op.model_dump(mode="python"), "identificador": "MB-OTRO"}
    )
    with pytest.raises(ValueError, match="duplicados"):
        repo.agregar(copia, huella_esperada=repo.huella())


def test_modelo_no_permite_valores_flotantes() -> None:
    with pytest.raises(ValueError, match="texto o Decimal"):
        AplicacionBancaria(expediente="FAC-1", importe=5.1)

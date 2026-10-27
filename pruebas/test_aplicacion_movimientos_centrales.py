"""Aplicación y reversión controlada de movimientos bancarios compartidos."""

from decimal import Decimal
from io import BytesIO

import pytest
from PIL import Image

from agente_comprobantes.control_financiero.archivos import almacen_para_excel
from agente_comprobantes.control_financiero.conciliacion import conciliar_flete
from agente_comprobantes.control_financiero.modelos import MovimientoBancario, OperacionFlete
from agente_comprobantes.control_financiero.repositorio_json import (
    RepositorioControlFletes,
)
from agente_comprobantes.control_financiero.repositorio_movimientos import (
    RepositorioMovimientosCentrales,
)
from agente_comprobantes.control_financiero.revision_pagos import preparar_revision_pago
from agente_comprobantes.control_financiero.servicio_movimientos import (
    adjuntar_voucher_central,
    aplicar_movimiento_central,
    documentar_movimiento_central,
    guardar_borrador_central,
    reabrir_movimiento_central,
    redistribuir_movimiento_central,
    revertir_aplicacion_central,
)
from agente_comprobantes.dominio.enumeraciones import Moneda


def imagen_png() -> bytes:
    salida = BytesIO()
    Image.new("RGB", (2, 2)).save(salida, format="PNG")
    return salida.getvalue()


@pytest.fixture
def ambiente(tmp_path):
    excel = tmp_path / "registros.xlsx"
    excel.write_bytes(b"no-modificar")
    control = RepositorioControlFletes(tmp_path / "control_fletes.json")
    for codigo in ("FAC-1", "FAC-2"):
        control.agregar(OperacionFlete(
            identificador=codigo,
            numero_factura=codigo,
            moneda=Moneda.PEN,
            monto_facturado=Decimal("1000"),
        ))
    central = RepositorioMovimientosCentrales(
        tmp_path / "movimientos_bancarios_centrales.json"
    )
    almacen = almacen_para_excel(excel)
    return excel, control, central, almacen


def crear(control, central, referencia="OP-100"):
    return guardar_borrador_central(
        central, control,
        banco="BCP",
        referencia=referencia,
        moneda=Moneda.PEN,
        importe_total="1000",
        aplicaciones=[("FAC-1", "400"), ("FAC-2", "600")],
        sustento="Voucher de transferencia compartida",
        huella_control=control.huella(),
        huella_central=central.huella(),
    )


def adjuntar(control, central, almacen, movimiento):
    return adjuntar_voucher_central(
        central, control, almacen, movimiento.identificador,
        nombre="voucher.png",
        contenido=imagen_png(),
        motivo="Se comprobó el voucher del movimiento compartido",
        confirmacion=True,
        huella_control=control.huella(),
        huella_central=central.huella(),
    )


def documentar(control, central, almacen, movimiento):
    return documentar_movimiento_central(
        central, control, almacen, movimiento.identificador,
        motivo="Se cotejaron banco, referencia e importes",
        confirmacion=True,
        huella_control=control.huella(),
        huella_central=central.huella(),
    )


def aplicar(control, central, almacen, movimiento):
    return aplicar_movimiento_central(
        central, control, almacen, movimiento.identificador,
        motivo="Distribución cotejada y autorizada por revisión humana",
        confirmacion=True,
        huella_control=control.huella(),
        huella_central=central.huella(),
    )


def preparar_documentado(control, central, almacen):
    movimiento = crear(control, central)
    adjuntar(control, central, almacen, movimiento)
    return documentar(control, central, almacen, movimiento)


def test_aplicacion_central_actualiza_varias_facturas_sin_duplicar(ambiente):
    _, control, central, almacen = ambiente
    creado = preparar_documentado(control, central, almacen)
    aplicado = aplicar(control, central, almacen, creado)

    assert aplicado.estado == "APLICADO"
    assert len(central.listar()) == 1
    for codigo, importe in (("FAC-1", Decimal("400")), ("FAC-2", Decimal("600"))):
        factura = control.obtener(codigo)
        assert len(factura.movimientos_bancarios) == 1
        pago = factura.movimientos_bancarios[0]
        assert pago.importe_aplicado == importe
        assert pago.verificada is True
        assert pago.referencia == aplicado.referencia
        assert pago.documento_respaldo == aplicado.respaldo
        assert pago.movimiento_central_id == aplicado.identificador
        assert conciliar_flete(factura).bancarizado_acreditado == importe
        assert (
            factura.revisiones[-1].cambios["movimiento_central_id"]
            == aplicado.identificador
        )


def test_reversion_resta_del_saldo_sin_borrar_evidencia(ambiente):
    _, control, central, almacen = ambiente
    creado = preparar_documentado(control, central, almacen)
    aplicado = aplicar(control, central, almacen, creado)
    revertido = revertir_aplicacion_central(
        central, control, aplicado.identificador,
        motivo="Distribución asignada a facturas incorrectas",
        confirmacion=True,
        huella_control=control.huella(),
        huella_central=central.huella(),
    )

    assert revertido.estado == "REVERTIDO"
    for codigo in ("FAC-1", "FAC-2"):
        factura = control.obtener(codigo)
        assert len(factura.movimientos_bancarios) == 1
        assert factura.movimientos_bancarios[0].verificada is False
        assert (
            factura.movimientos_bancarios[0].movimiento_central_id
            == creado.identificador
        )
        assert conciliar_flete(factura).bancarizado_acreditado == 0
        assert any(
            clave.endswith(".verificada")
            for clave in factura.revisiones[-1].cambios
        )


def test_reaplicar_tras_reversion_actualiza_importes_sin_nuevos_pagos(ambiente):
    _, control, central, almacen = ambiente
    creado = preparar_documentado(control, central, almacen)
    aplicado = aplicar(control, central, almacen, creado)
    revertir_aplicacion_central(
        central, control, aplicado.identificador,
        motivo="Se detectó un error de distribución en la revisión",
        confirmacion=True,
        huella_control=control.huella(),
        huella_central=central.huella(),
    )
    reabrir_movimiento_central(
        central, control, aplicado.identificador,
        motivo="Se corregirá la distribución antes de volver a aplicar",
        confirmacion=True,
        huella_control=control.huella(),
        huella_central=central.huella(),
    )
    redistribuir_movimiento_central(
        central, control, aplicado.identificador,
        aplicaciones=[("FAC-1", "450"), ("FAC-2", "550")],
        motivo="Importes corregidos según el voucher cotejado",
        confirmacion=True,
        huella_control=control.huella(),
        huella_central=central.huella(),
    )
    documentar(control, central, almacen, aplicado)
    final = aplicar(control, central, almacen, aplicado)

    assert final.estado == "APLICADO"
    assert len(control.obtener("FAC-1").movimientos_bancarios) == 1
    assert len(control.obtener("FAC-2").movimientos_bancarios) == 1
    assert control.obtener("FAC-1").movimientos_bancarios[0].importe_aplicado == 450
    assert control.obtener("FAC-2").movimientos_bancarios[0].importe_aplicado == 550
    assert conciliar_flete(control.obtener("FAC-1")).bancarizado_acreditado == 450
    assert conciliar_flete(control.obtener("FAC-2")).bancarizado_acreditado == 550


def test_aplicar_bloquea_referencia_historica_anadida_despues_de_documentar(ambiente):
    _, control, central, almacen = ambiente
    creado = preparar_documentado(control, central, almacen)
    factura = control.obtener("FAC-1")
    pago = MovimientoBancario(
        importe_aplicado=Decimal("100"),
        moneda=Moneda.PEN,
        referencia=creado.referencia,
        documento_respaldo="adjunto:" + "b" * 64 + ".pdf",
        verificada=False,
    )
    control.actualizar(factura.model_copy(update={"movimientos_bancarios": [pago]}))
    with pytest.raises(ValueError, match="histórico|ajeno al movimiento central"):
        aplicar(control, central, almacen, creado)
    assert central.obtener(creado.identificador).estado == "DOCUMENTADO"
    assert not control.obtener("FAC-2").movimientos_bancarios


def test_pago_central_no_se_revierte_desde_revision_individual(ambiente):
    _, control, central, almacen = ambiente
    creado = preparar_documentado(control, central, almacen)
    aplicar(control, central, almacen, creado)
    factura = control.obtener("FAC-1")

    with pytest.raises(ValueError, match="movimiento central"):
        preparar_revision_pago(
            factura,
            indice=0,
            acreditar=False,
            motivo="Se intentó revertir por el formulario individual",
            confirmacion=True,
            version_esperada=len(factura.revisiones),
        )


def test_lote_de_control_rechaza_huella_obsoleta(ambiente):
    _, control, _, _ = ambiente
    factura = control.obtener("FAC-1")
    anterior = control.huella()
    control.actualizar(
        control.obtener("FAC-2").model_copy(update={"proveedor": "Actualizado"})
    )
    with pytest.raises(ValueError, match="cambió"):
        control.actualizar_lote(
            [factura.model_copy(update={"proveedor": "Obsoleto"})],
            huella_esperada=anterior,
        )
    assert control.obtener("FAC-1").proveedor != "Obsoleto"


def test_no_se_aplica_un_movimiento_sin_revisar_documentacion(ambiente):
    _, control, central, almacen = ambiente
    movimiento = crear(control, central)
    with pytest.raises(ValueError, match="documenta"):
        aplicar(control, central, almacen, movimiento)
    assert central.obtener(movimiento.identificador).estado == "BORRADOR"


def test_reintento_finaliza_aplicacion_si_falla_actualizacion_central(ambiente):
    _, control, central, almacen = ambiente
    creado = preparar_documentado(control, central, almacen)
    actualizar_original = central.actualizar

    def fallo_controlado(*args, **kwargs):
        raise OSError("fallo simulado al guardar estado central")

    central.actualizar = fallo_controlado
    with pytest.raises(OSError, match="simulado"):
        aplicar(control, central, almacen, creado)
    central.actualizar = actualizar_original

    assert central.obtener(creado.identificador).estado == "DOCUMENTADO"
    assert all(
        control.obtener(codigo).movimientos_bancarios[0].verificada
        for codigo in ("FAC-1", "FAC-2")
    )
    recuperado = aplicar(control, central, almacen, creado)
    assert recuperado.estado == "APLICADO"
    assert all(
        len(control.obtener(codigo).movimientos_bancarios) == 1
        for codigo in ("FAC-1", "FAC-2")
    )


def test_reintento_finaliza_reversion_si_falla_actualizacion_central(ambiente):
    _, control, central, almacen = ambiente
    creado = preparar_documentado(control, central, almacen)
    aplicado = aplicar(control, central, almacen, creado)
    actualizar_original = central.actualizar

    def fallo_controlado(*args, **kwargs):
        raise OSError("fallo simulado al guardar estado central")

    central.actualizar = fallo_controlado
    with pytest.raises(OSError, match="simulado"):
        revertir_aplicacion_central(
            central, control, aplicado.identificador,
            motivo="Se revierte para recuperar una asignación errónea",
            confirmacion=True,
            huella_control=control.huella(),
            huella_central=central.huella(),
        )
    central.actualizar = actualizar_original

    assert central.obtener(creado.identificador).estado == "APLICADO"
    assert all(
        not control.obtener(codigo).movimientos_bancarios[0].verificada
        for codigo in ("FAC-1", "FAC-2")
    )
    recuperado = revertir_aplicacion_central(
        central, control, aplicado.identificador,
        motivo="Se finaliza la reversión previamente registrada",
        confirmacion=True,
        huella_control=control.huella(),
        huella_central=central.huella(),
    )
    assert recuperado.estado == "REVERTIDO"
    assert all(
        len(control.obtener(codigo).movimientos_bancarios) == 1
        for codigo in ("FAC-1", "FAC-2")
    )

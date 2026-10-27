"""Persistencia v2, distribución, voucher y decisiones humanas del registro central."""

import json
from decimal import Decimal
from io import BytesIO

import pytest
from PIL import Image

from agente_comprobantes.control_financiero.archivos import almacen_para_excel
from agente_comprobantes.control_financiero.modelos import OperacionFlete
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
    reabrir_movimiento_central,
    redistribuir_movimiento_central,
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
    central = RepositorioMovimientosCentrales(tmp_path / "centrales.json")
    almacen = almacen_para_excel(excel)
    return excel, control, central, almacen


def crear(control, central, referencia="OP-100", aplicaciones=None):
    return guardar_borrador_central(
        central, control,
        banco="BCP",
        referencia=referencia,
        moneda=Moneda.PEN,
        importe_total="1000",
        aplicaciones=aplicaciones or [("FAC-1", "400"), ("FAC-2", "600")],
        sustento="Voucher de transferencia compartida",
        huella_control=control.huella(),
        huella_central=central.huella(),
    )


def distribuir(control, central, identificador, aplicaciones, **opciones):
    datos = {
        "aplicaciones": aplicaciones,
        "motivo": "Se corrigieron aplicaciones después del cotejo",
        "confirmacion": True,
        "huella_control": control.huella(),
        "huella_central": central.huella(),
    }
    datos.update(opciones)
    return redistribuir_movimiento_central(
        central, control, identificador, **datos
    )


def adjuntar(control, central, almacen, identificador, **opciones):
    datos = {
        "nombre": "voucher.png",
        "contenido": imagen_png(),
        "motivo": "Se comprobó el voucher del movimiento compartido",
        "confirmacion": True,
        "huella_control": control.huella(),
        "huella_central": central.huella(),
    }
    datos.update(opciones)
    return adjuntar_voucher_central(
        central, control, almacen, identificador, **datos
    )


def documentar(control, central, almacen, identificador, **opciones):
    datos = {
        "motivo": "Se cotejaron banco, referencia y asignaciones",
        "confirmacion": True,
        "huella_control": control.huella(),
        "huella_central": central.huella(),
    }
    datos.update(opciones)
    return documentar_movimiento_central(
        central, control, almacen, identificador, **datos
    )


def test_v2_guarda_movimientos_y_aplicaciones_separados(ambiente):
    excel, control, central, _ = ambiente
    anterior = control.huella()
    movimiento = crear(control, central)
    data = json.loads(central.ruta.read_text(encoding="utf-8"))
    assert data["version"] == 2
    assert "aplicaciones" not in data["movimientos"][0]
    assert data["aplicaciones"] == [
        {"movimiento_id": movimiento.identificador, "expediente": "FAC-1",
         "importe": "400"},
        {"movimiento_id": movimiento.identificador, "expediente": "FAC-2",
         "importe": "600"},
    ]
    assert central.obtener(movimiento.identificador) == movimiento
    assert control.huella() == anterior
    assert excel.read_bytes() == b"no-modificar"


def test_carga_v1_y_migra_solo_al_guardar(ambiente):
    _, control, central, _ = ambiente
    inicial = crear(control, central)
    legado = {
        "version": 1,
        "movimientos": [inicial.model_dump(mode="json")],
    }
    central.ruta.write_text(json.dumps(legado), encoding="utf-8")
    assert central.listar() == [inicial]
    assert json.loads(central.ruta.read_text())["version"] == 1
    nuevo = inicial.model_copy(update={
        "identificador": "MB-SEGUNDO",
        "referencia": "OP-200",
    })
    central.agregar(nuevo, huella_esperada=central.huella())
    assert len(central.listar()) == 2
    assert json.loads(central.ruta.read_text())["version"] == 2


@pytest.mark.parametrize(
    "aplicaciones",
    [
        [{"movimiento_id": "MB-INEXISTENTE", "expediente": "FAC-1", "importe": "10"}],
        [{"movimiento_id": "MB-X", "expediente": "FAC-1", "importe": "10"}] * 2,
    ],
)
def test_v2_rechaza_aplicaciones_corruptas(tmp_path, aplicaciones):
    central = RepositorioMovimientosCentrales(tmp_path / "centrales.json")
    central.ruta.write_text(
        json.dumps({"version": 2, "movimientos": [], "aplicaciones": aplicaciones}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        central.listar()


def test_redistribuir_sin_crear_segundo_voucher(ambiente):
    _, control, central, _ = ambiente
    inicial = crear(control, central)
    nuevo = distribuir(control, central, inicial.identificador, [
        ("FAC-1", "650"), ("FAC-2", "200"),
    ])
    assert len(central.listar()) == 1
    assert nuevo.sin_asignar == Decimal("150")
    assert len(nuevo.revisiones) == 1
    assert nuevo.revisiones[0].accion == "REDISTRIBUIR"
    assert central.obtener(inicial.identificador) == nuevo


def test_redistribucion_invalida_no_altera_json(ambiente):
    _, control, central, _ = ambiente
    creado = crear(control, central)
    antes = central.ruta.read_bytes()
    with pytest.raises(ValueError, match="supera"):
        distribuir(control, central, creado.identificador, [
            ("FAC-1", "900"), ("FAC-2", "800"),
        ])
    assert central.ruta.read_bytes() == antes


def test_voucher_y_revision_documental_no_acreditan_saldos(ambiente):
    excel, control, central, almacen = ambiente
    creado = crear(control, central)
    original = control.huella()
    vinculado = adjuntar(control, central, almacen, creado.identificador)
    assert vinculado.estado == "BORRADOR"
    assert vinculado.respaldo.startswith("adjunto:")
    assert almacen.abrir(vinculado.respaldo)[0] == imagen_png()
    documentado = documentar(control, central, almacen, creado.identificador)
    assert documentado.estado == "DOCUMENTADO"
    assert [r.accion for r in documentado.revisiones] == [
        "VINCULAR_EVIDENCIA", "DOCUMENTAR",
    ]
    assert control.huella() == original
    assert excel.read_bytes() == b"no-modificar"
    assert all(not f.movimientos_bancarios for f in control.listar())


def test_documentar_sin_archivo_valido_prohibido(ambiente):
    _, control, central, almacen = ambiente
    creado = crear(control, central)
    with pytest.raises(ValueError, match="adjunta"):
        documentar(control, central, almacen, creado.identificador)
    assert central.obtener(creado.identificador).estado == "BORRADOR"


def test_documentado_inmutable_hasta_reversion(ambiente):
    _, control, central, almacen = ambiente
    creado = crear(control, central)
    adjuntar(control, central, almacen, creado.identificador)
    documentar(control, central, almacen, creado.identificador)
    with pytest.raises(ValueError, match="documentado"):
        distribuir(control, central, creado.identificador, [
            ("FAC-1", "500"), ("FAC-2", "500"),
        ])


def test_adjuntar_voucher_duplicado_entre_movimientos(ambiente):
    _, control, central, almacen = ambiente
    primero = crear(control, central)
    segundo = crear(control, central, referencia="OP-OTRA", aplicaciones=[
        ("FAC-1", "100"), ("FAC-2", "100"),
    ])
    adjuntar(control, central, almacen, primero.identificador)
    with pytest.raises(ValueError, match="mismo voucher"):
        adjuntar(control, central, almacen, segundo.identificador)


def test_revision_obsoleta_no_reescribe_movimiento(ambiente):
    _, control, central, almacen = ambiente
    creado = crear(control, central)
    antigua = central.huella()
    adjuntar(control, central, almacen, creado.identificador)
    antes = central.ruta.read_bytes()
    with pytest.raises(ValueError, match="cambió"):
        documentar(
            control, central, almacen, creado.identificador,
            huella_central=antigua,
        )
    assert central.ruta.read_bytes() == antes


def test_reapertura_conserva_adjuntos_e_historial(ambiente):
    _, control, central, almacen = ambiente
    creado = crear(control, central)
    adjuntar(control, central, almacen, creado.identificador)
    documentar(control, central, almacen, creado.identificador)
    reabierto = reabrir_movimiento_central(
        central, control, creado.identificador,
        motivo="El importe de la segunda factura necesita corrección",
        confirmacion=True,
        huella_control=control.huella(), huella_central=central.huella(),
    )
    assert reabierto.estado == "BORRADOR"
    assert reabierto.respaldo is not None
    assert [r.accion for r in reabierto.revisiones] == [
        "VINCULAR_EVIDENCIA", "DOCUMENTAR", "REABRIR",
    ]
    corregido = distribuir(control, central, creado.identificador, [
        ("FAC-1", "450"), ("FAC-2", "550"),
    ])
    assert corregido.sin_asignar == 0
    assert len(central.listar()) == 1

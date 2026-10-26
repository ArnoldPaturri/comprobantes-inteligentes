"""Pruebas integradas de asociación real de archivos con pagos y ajustes."""

from decimal import Decimal
from io import BytesIO

import pytest
from PIL import Image

from agente_comprobantes.control_financiero.adjuntos import (
    guardar_adjunto_existente,
    guardar_ajuste_con_archivo,
)
from agente_comprobantes.control_financiero.archivos import almacen_para_excel
from agente_comprobantes.control_financiero.modelos import (
    MovimientoBancario,
    OperacionFlete,
)
from agente_comprobantes.control_financiero.repositorio_json import (
    RepositorioControlFletes,
)
from agente_comprobantes.dominio.enumeraciones import Moneda


def imagen() -> bytes:
    stream = BytesIO()
    Image.new("RGB", (4, 4)).save(stream, format="PNG")
    return stream.getvalue()


def operacion() -> OperacionFlete:
    return OperacionFlete(
        identificador="FAC-1",
        numero_factura="F001-1",
        moneda=Moneda.PEN,
        monto_facturado=Decimal("200"),
        es_flete=True,
        detraccion_aplica=True,
        movimientos_bancarios=[
            MovimientoBancario(
                importe_aplicado="100",
                moneda=Moneda.PEN,
                referencia="OP-001",
                documento_respaldo="pago_ocr.png",
                verificada=True,
            )
        ],
    )


def test_carga_pago_revoca_validacion_anterior_y_preserva_excel(tmp_path) -> None:
    excel = tmp_path / "registros.xlsx"
    excel.write_bytes(b"archivo-original")
    repo = RepositorioControlFletes(tmp_path / "control_fletes.json")
    repo.agregar(operacion())
    almacen = almacen_para_excel(excel)
    actualizado = guardar_adjunto_existente(
        repo, almacen, "FAC-1",
        destino="pago", indice=0, nombre="voucher.png", contenido=imagen(),
        motivo="Se reemplaza archivo indicado por comprobante escaneado",
        confirmacion=True, version_esperada=0,
    )
    pago = actualizado.movimientos_bancarios[0]
    assert not pago.verificada
    assert pago.documento_respaldo.startswith("adjunto:")
    assert almacen.abrir(pago.documento_respaldo)[1] == "png"
    assert not actualizado.conciliacion_cerrada
    assert excel.read_bytes() == b"archivo-original"
    assert repo.obtener("FAC-1") == actualizado


def test_error_en_vinculacion_no_guarda_archivo(tmp_path) -> None:
    excel = tmp_path / "registros.xlsx"
    repo = RepositorioControlFletes(tmp_path / "control_fletes.json")
    repo.agregar(operacion())
    almacen = almacen_para_excel(excel)
    with pytest.raises(ValueError, match="cambió"):
        guardar_adjunto_existente(
            repo, almacen, "FAC-1",
            destino="pago", indice=0, nombre="voucher.png", contenido=imagen(),
            motivo="Se revisó comprobante", confirmacion=True, version_esperada=5,
        )
    assert not (tmp_path / "adjuntos_financieros").exists()


def test_detraccion_con_archivo_real_no_se_acredita(tmp_path) -> None:
    repo = RepositorioControlFletes(tmp_path / "control_fletes.json")
    repo.agregar(operacion())
    almacen = almacen_para_excel(tmp_path / "registros.xlsx")
    actualizado = guardar_ajuste_con_archivo(
        repo, almacen, "FAC-1",
        tipo="detraccion", referencia="SPOT-123", monto="20.00", numero=None,
        nombre="constancia.png", contenido=imagen(),
        motivo="Documento registrado para revisión posterior",
        confirmacion=True, version_esperada=0,
    )
    deposito = actualizado.depositos_detraccion[0]
    assert not deposito.verificada
    assert deposito.documento_respaldo.startswith("adjunto:")
    assert almacen.abrir(deposito.documento_respaldo)[0] == imagen()
    assert actualizado.revisiones[-1].cambios["archivo_original"] == "constancia.png"


def test_nota_credito_con_archivo_tambien_funciona(tmp_path) -> None:
    repo = RepositorioControlFletes(tmp_path / "control_fletes.json")
    repo.agregar(operacion())
    actualizado = guardar_ajuste_con_archivo(
        repo, almacen_para_excel(tmp_path / "registros.xlsx"), "FAC-1",
        tipo="nota_credito", referencia="NC-1", monto="35", numero="FC01-1",
        nombre="nota.png", contenido=imagen(),
        motivo="Nota registrada con su imagen original",
        confirmacion=True, version_esperada=0,
    )
    assert actualizado.notas_credito[0].numero == "FC01-1"
    assert not actualizado.notas_credito[0].verificada


def test_archivo_inválido_no_modifica_json(tmp_path) -> None:
    repo = RepositorioControlFletes(tmp_path / "control_fletes.json")
    repo.agregar(operacion())
    json_path = tmp_path / "control_fletes.json"
    antes = json_path.read_bytes()
    with pytest.raises(ValueError):
        guardar_ajuste_con_archivo(
            repo, almacen_para_excel(tmp_path / "registros.xlsx"), "FAC-1",
            tipo="nota_credito", referencia="NC-1", monto="35", numero="FC01-1",
            nombre="nota.html", contenido=b"<script>hola</script>",
            motivo="Documento rechazado en validación",
            confirmacion=True, version_esperada=0,
        )
    assert json_path.read_bytes() == antes

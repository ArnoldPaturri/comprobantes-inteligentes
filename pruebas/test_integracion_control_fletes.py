"""Integración con el Excel heredado y almacenamiento aislado de fletes."""

from decimal import Decimal

import pytest

from agente_comprobantes.control_financiero import conciliar_flete
from agente_comprobantes.control_financiero.integracion import (
    crear_borrador_desde_documentos,
    crear_borrador_desde_repositorio,
)
from agente_comprobantes.control_financiero.modelos import SituacionControl
from agente_comprobantes.control_financiero.repositorio_json import (
    RepositorioControlFletes,
)
from agente_comprobantes.dominio import (
    Diagnostico,
    EstadoVerificacion,
    EstadoVinculacionPago,
    Moneda,
    RegistroCotizacion,
    RegistroFactura,
    RegistroPago,
    ResultadoConciliacion,
    TipoDocumento,
)
from agente_comprobantes.repositorios.repositorio_excel import RepositorioExcel


def factura(**cambios: object) -> RegistroFactura:
    datos = {
        "invoice_id": "FAC-01",
        "quotation_code": "COT-01",
        "invoice_number": "F001-12",
        "provider": "Empresa Transporte",
        "invoiced_amount": Decimal("1000"),
        "currency": Moneda.PEN,
        "verification_status": EstadoVerificacion.VERIFIED,
        "source_hash": "sha256-factura",
        "source_files": ["factura.pdf"],
    }
    datos.update(cambios)
    return RegistroFactura(**datos)


def cotizacion(**cambios: object) -> RegistroCotizacion:
    datos = {
        "quotation_code": "COT-01",
        "quoted_amount": Decimal("900"),
        "currency": Moneda.PEN,
        "verification_status": EstadoVerificacion.VERIFIED,
        "source_hash": "sha256-cotizacion",
        "source_files": ["cotizacion.pdf"],
    }
    datos.update(cambios)
    return RegistroCotizacion(**datos)


def pago(**cambios: object) -> RegistroPago:
    datos = {
        "payment_id": "PAG-01",
        "quotation_code": "COT-01",
        "invoice_id": "FAC-01",
        "payment_type": TipoDocumento.BANK_TRANSFER,
        "paid_amount": Decimal("1000"),
        "currency": Moneda.PEN,
        "operation_number": "OP-1288",
        "verification_status": EstadoVerificacion.VERIFIED,
        "reconciliation_status": EstadoVinculacionPago.RECONCILED,
        "source_hash": "sha256-pago",
        "source_files": ["voucher.pdf"],
    }
    datos.update(cambios)
    return RegistroPago(**datos)


def test_documentos_convertidos_no_acreditan_pago_por_ocr() -> None:
    borrador = crear_borrador_desde_documentos(factura(), cotizacion(), [pago()])
    movimiento = borrador.operacion.movimientos_bancarios[0]
    assert movimiento.importe_aplicado == Decimal("1000")
    assert not movimiento.verificada
    assert borrador.operacion.monto_cotizado == Decimal("900")
    assert borrador.operacion.detraccion_aplica is None
    assert conciliar_flete(borrador.operacion).situacion == SituacionControl.PENDIENTE


def test_factura_sin_monto_no_produce_borrador_engañoso() -> None:
    with pytest.raises(ValueError, match="importe positivo"):
        crear_borrador_desde_documentos(factura(invoiced_amount=None))


def test_factura_sin_numero_no_inventa_referencia() -> None:
    with pytest.raises(ValueError, match="número legible"):
        crear_borrador_desde_documentos(factura(invoice_number=None))


def test_pago_con_moneda_desconocida_no_se_acredita() -> None:
    borrador = crear_borrador_desde_documentos(
        factura(), cotizacion(), [pago(currency=None)]
    )
    assert not borrador.operacion.movimientos_bancarios
    assert any("moneda" in advertencia for advertencia in borrador.advertencias)


def test_rechazar_pago_de_otra_factura() -> None:
    with pytest.raises(ValueError, match="no corresponde"):
        crear_borrador_desde_documentos(
            factura(), cotizacion(), [pago(invoice_id="FAC-OTRA")]
        )


class RepositorioSimulado:
    def __init__(self) -> None:
        self.consultas = []

    def obtener_factura(self, identificador: str) -> RegistroFactura | None:
        self.consultas.append(("obtener_factura", identificador))
        return factura()

    def obtener_cotizacion(self, codigo: str) -> RegistroCotizacion | None:
        self.consultas.append(("obtener_cotizacion", codigo))
        return cotizacion()

    def leer_hoja(self, hoja: str) -> list[dict[str, object]]:
        self.consultas.append(("leer_hoja", hoja))
        return [{"ID Factura": "FAC-01", "ID Pago": "PAG-01"}]

    def obtener_pago(self, identificador: str) -> RegistroPago | None:
        self.consultas.append(("obtener_pago", identificador))
        return pago()


def test_lector_de_repositorio_consulta_registros_sin_mutar() -> None:
    repositorio = RepositorioSimulado()
    borrador = crear_borrador_desde_repositorio(repositorio, "FAC-01")
    assert borrador.operacion.numero_factura == "F001-12"
    assert len(borrador.operacion.movimientos_bancarios) == 1
    assert repositorio.consultas == [
        ("obtener_factura", "FAC-01"),
        ("obtener_cotizacion", "COT-01"),
        ("leer_hoja", "PAGOS"),
        ("obtener_pago", "PAG-01"),
    ]


def test_guardado_json_separado_y_atomicidad(tmp_path) -> None:
    destino = tmp_path / "controles" / "control_fletes.json"
    repositorio = RepositorioControlFletes(destino)
    assert repositorio.listar() == []

    operacion = crear_borrador_desde_documentos(factura()).operacion
    repositorio.agregar(operacion)
    assert repositorio.obtener("fac-01") == operacion
    assert destino.exists()

    with pytest.raises(ValueError, match="Ya existe"):
        repositorio.agregar(operacion)
    assert len(repositorio.listar()) == 1

    actualizado = operacion.model_copy(update={"numero_guia": "EG07-642"})
    repositorio.actualizar(actualizado)
    assert repositorio.obtener("FAC-01").numero_guia == "EG07-642"


def test_no_sobrescribir_json_con_version_desconocida(tmp_path) -> None:
    destino = tmp_path / "control.json"
    contenido = '{"version": 999, "operaciones": []}'
    destino.write_text(contenido, encoding="utf-8")
    repositorio = RepositorioControlFletes(destino)
    with pytest.raises(ValueError, match="formato inválido"):
        repositorio.agregar(crear_borrador_desde_documentos(factura()).operacion)
    assert destino.read_text(encoding="utf-8") == contenido


def test_integracion_lee_excel_real_sin_cambiar_su_contenido(tmp_path) -> None:
    ruta = tmp_path / "registros.xlsx"
    repositorio = RepositorioExcel(ruta)
    presupuesto = cotizacion()
    documento = factura()
    repositorio.agregar_cotizacion(presupuesto)
    repositorio.agregar_factura(
        documento,
        presupuesto,
        ResultadoConciliacion(
            quoted_amount=Decimal("900"),
            invoiced_amount=Decimal("1000"),
            difference=Decimal("100"),
            deviation_percent=Decimal("11.11"),
            diagnosis=Diagnostico.ABOVE,
        ),
    )
    repositorio.agregar_pago(pago())
    contenido_original = ruta.read_bytes()

    borrador = crear_borrador_desde_repositorio(repositorio, "FAC-01")

    assert borrador.operacion.identificador == "FAC-01"
    assert borrador.operacion.numero_factura == "F001-12"
    assert borrador.operacion.monto_facturado == Decimal("1000")
    assert borrador.operacion.monto_cotizado == Decimal("900")
    assert len(borrador.operacion.movimientos_bancarios) == 1
    assert not borrador.operacion.movimientos_bancarios[0].verificada
    assert ruta.read_bytes() == contenido_original

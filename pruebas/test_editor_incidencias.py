"""Pruebas de corrección documental segura sobre expedientes ya importados."""

from decimal import Decimal

import pytest

from agente_comprobantes.control_financiero.editor_incidencias import (
    guardar_desglose,
    guardar_reclasificacion_efectivo,
    preparar_desglose,
    preparar_reclasificacion_efectivo,
)
from agente_comprobantes.control_financiero.modelos import (
    DatosOrigenExcel,
    MovimientoBancario,
    OperacionFlete,
)
from agente_comprobantes.control_financiero.repositorio_json import (
    RepositorioControlFletes,
)
from agente_comprobantes.dominio.enumeraciones import Moneda


def expediente(
    *,
    referencia: str = "6537194 Y 340464",
    monto: str = "7000",
    verificada: bool = False,
    nombre: str = "FAC-1",
) -> OperacionFlete:
    return OperacionFlete(
        identificador=nombre,
        numero_factura="F001-" + nombre,
        proveedor="Transportes Sur",
        moneda=Moneda.PEN,
        monto_facturado=Decimal("8000"),
        movimientos_bancarios=[
            MovimientoBancario(
                referencia=referencia,
                moneda=Moneda.PEN,
                importe_aplicado=Decimal(monto),
                verificada=verificada,
                documento_respaldo="voucher_anterior.pdf",
            ),
        ],
        datos_origen=DatosOrigenExcel(
            archivo="FLETES.xlsx",
            huella_archivo="huella-de-prueba",
            hoja="Detalle",
            fila=7,
            campos={"NRO. BANCARIZACIÓN": referencia},
        ),
    )


def desglosar(op, **kwargs):
    valores = dict(
        indice=0,
        asignaciones=[("6537194", "4000.00"), ("340464", "3000.00")],
        motivo="Vouchers individuales revisados por el operador",
        confirmacion=True,
        version_esperada=0,
    )
    valores.update(kwargs)
    return preparar_desglose(op, **valores)


def test_desglosar_conserva_total_y_orig_and_no_acredita() -> None:
    op = expediente()
    antes = op.model_dump(mode="json")
    nuevo = desglosar(op)
    assert op.model_dump(mode="json") == antes
    assert len(nuevo.movimientos_bancarios) == 2
    assert {p.referencia for p in nuevo.movimientos_bancarios} == {
        "6537194", "340464",
    }
    assert sum(p.importe_aplicado for p in nuevo.movimientos_bancarios) == 7000
    assert all(not p.verificada for p in nuevo.movimientos_bancarios)
    assert all(p.documento_respaldo is None for p in nuevo.movimientos_bancarios)
    assert nuevo.datos_origen == op.datos_origen
    assert nuevo.revisiones[-1].cambios["referencia_original"] == (
        "6537194 Y 340464"
    )
    assert not nuevo.conciliacion_cerrada


@pytest.mark.parametrize(
    ("asignaciones", "texto"),
    [
        ([("6537194", "4000"), ("340464", "2999")], "suma"),
        ([("6537194", "4000"), ("340464", "3000.01")], "suma"),
        ([("6537194", "4000"), ("6537194", "3000")], "coincidir"),
        ([("6537194", "4000"), ("999999", "3000")], "coincidir"),
        ([("6537194", "4000.999"), ("340464", "2999.001")], "decimales"),
        ([("6537194", "7000")], "importe por cada referencia"),
    ],
)
def test_rechazar_desgloses_con_errores(asignaciones, texto) -> None:
    with pytest.raises(ValueError, match=texto):
        desglosar(expediente(), asignaciones=asignaciones)


def test_no_desglosar_acreditado_ni_viejo_ni_sin_confirmacion() -> None:
    with pytest.raises(ValueError, match="retira"):
        desglosar(expediente(verificada=True))
    with pytest.raises(ValueError, match="cambió"):
        desglosar(expediente(), version_esperada=3)
    with pytest.raises(ValueError, match="Confirma"):
        desglosar(expediente(), confirmacion=False)


def test_desglose_rechaza_referencia_en_otra_factura() -> None:
    otro = expediente(referencia="6537194", nombre="FAC-2")
    with pytest.raises(ValueError, match="otra factura"):
        desglosar(expediente(), otras_operaciones=[otro])


def test_reclasificar_efectivo_aparta_pago_sin_perder_importes() -> None:
    op = expediente(referencia="EFECTIVO?", monto="40")
    antes = op.model_dump(mode="json")
    actualizado = preparar_reclasificacion_efectivo(
        op,
        indice=0,
        motivo="Se corrige marca de efectivo no sustentada",
        confirmacion=True,
        version_esperada=0,
    )
    assert op.model_dump(mode="json") == antes
    assert actualizado.movimientos_bancarios == []
    assert len(actualizado.declaraciones_por_aclarar) == 1
    declaracion = actualizado.declaraciones_por_aclarar[0]
    assert declaracion.referencia_original == "EFECTIVO?"
    assert declaracion.importe_declarado == Decimal("40")
    assert declaracion.respaldo_original == "voucher_anterior.pdf"
    assert actualizado.datos_origen == op.datos_origen
    assert actualizado.revisiones[0].cambios["accion"] == "reclasificar_efectivo"


def test_no_reclasificar_transferencia_ni_pago_acreditado() -> None:
    op = expediente(referencia="OP-123")
    with pytest.raises(ValueError, match="efectivo"):
        preparar_reclasificacion_efectivo(
            op, indice=0, motivo="Corrección de medio de pago",
            confirmacion=True, version_esperada=0,
        )
    with pytest.raises(ValueError, match="retira"):
        preparar_reclasificacion_efectivo(
            expediente(referencia="EFECTIVO", verificada=True),
            indice=0, motivo="Corrección de efectivo previamente acreditado",
            confirmacion=True, version_esperada=0,
        )


def test_guardado_json_es_atomico_y_excel_original_se_conserva(tmp_path) -> None:
    archivo_excel = tmp_path / "registros.xlsx"
    archivo_excel.write_bytes(b"excel-sin-modificar")
    repo = RepositorioControlFletes(tmp_path / "control_fletes.json")
    repo.agregar(expediente())
    cambio = guardar_desglose(
        repo,
        "FAC-1",
        indice=0,
        asignaciones=[("6537194", "4000"), ("340464", "3000")],
        motivo="Distribución manual sustentada por vouchers",
        confirmacion=True,
        version_esperada=0,
    )
    assert len(repo.obtener("FAC-1").movimientos_bancarios) == 2
    assert archivo_excel.read_bytes() == b"excel-sin-modificar"
    antes = (tmp_path / "control_fletes.json").read_bytes()
    with pytest.raises(ValueError, match="cambió"):
        guardar_desglose(
            repo, "FAC-1", indice=0,
            asignaciones=[("6537194", "4000"), ("340464", "3000")],
            motivo="Reintento con versión antigua",
            confirmacion=True, version_esperada=0,
        )
    assert (tmp_path / "control_fletes.json").read_bytes() == antes
    assert cambio.datos_origen.fila == 7


def test_reclasificacion_persiste_y_mantiene_historial(tmp_path) -> None:
    repo = RepositorioControlFletes(tmp_path / "control.json")
    repo.agregar(expediente(referencia="EFECTIVO"))
    salida = guardar_reclasificacion_efectivo(
        repo, "FAC-1", indice=0,
        motivo="Registro de efectivo requiere comprobación",
        confirmacion=True, version_esperada=0,
    )
    assert salida.movimientos_bancarios == []
    assert repo.obtener("FAC-1").declaraciones_por_aclarar[0].importe_declarado == 7000

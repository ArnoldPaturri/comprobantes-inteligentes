"""Los diagnósticos de expedientes existentes son de solo lectura."""

from decimal import Decimal

from agente_comprobantes.control_financiero.auditoria_expedientes import (
    auditar_expedientes,
)
from agente_comprobantes.control_financiero.editor_incidencias import (
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


def op(numero: str, referencia: str) -> OperacionFlete:
    return OperacionFlete(
        identificador=f"FAC-{numero}",
        numero_factura=numero,
        proveedor="Transportes Sur",
        moneda=Moneda.PEN,
        monto_facturado=Decimal("1000"),
        movimientos_bancarios=[
            MovimientoBancario(
                moneda=Moneda.PEN,
                importe_aplicado=Decimal("500"),
                referencia=referencia,
                verificada=False,
            )
        ],
    )


def test_diagnosticar_efectivo_previamente_registrado(tmp_path) -> None:
    repo = RepositorioControlFletes(tmp_path / "control.json")
    repo.agregar(op("F001-21", "EFECTIVO?"))
    anterior = (tmp_path / "control.json").read_bytes()
    hallazgos = auditar_expedientes(repo.listar())
    assert len(hallazgos) == 1
    assert hallazgos[0].tipo == "EFECTIVO POR CONFIRMAR"
    assert hallazgos[0].identificador == "FAC-F001-21"
    assert (tmp_path / "control.json").read_bytes() == anterior


def test_referencia_real_compartida_entre_facturas() -> None:
    hallazgos = auditar_expedientes([
        op("F001-21", "74200111.0"),
        op("F001-22", "74200111"),
    ])
    assert len(hallazgos) == 2
    assert all(h.tipo == "REFERENCIA COMPARTIDA" for h in hallazgos)
    assert {h.identificador for h in hallazgos} == {
        "FAC-F001-21", "FAC-F001-22",
    }


def test_etiqueta_efectivo_no_es_referencia_compartida() -> None:
    hallazgos = auditar_expedientes([
        op("F001-21", "EFECTIVO"),
        op("F001-22", "EFECTIVO"),
    ])
    assert len(hallazgos) == 2
    assert all(h.tipo == "EFECTIVO SIN OPERACIÓN" for h in hallazgos)


def test_referencias_multiples_conservan_dato_original() -> None:
    doc = op("F001-23", "6537194 Y 340464")
    doc.datos_origen = DatosOrigenExcel(
        huella_archivo="abc",
        hoja="Detalle",
        fila=7,
        campos={"NRO. BANCARIZACIÓN": "6537194 Y 340464"},
    )
    antes = doc.model_dump(mode="json")
    hallazgos = auditar_expedientes([doc])
    assert any(h.tipo == "REFERENCIAS MÚLTIPLES" for h in hallazgos)
    assert doc.model_dump(mode="json") == antes


def test_sin_referencias_ambiguas_no_hay_hallazgos() -> None:
    assert auditar_expedientes([op("F001-23", "74200111")]) == ()



def test_desglosado_ya_no_tiene_alarma_historica_activa() -> None:
    expediente = op("F001-25", "6537194 Y 340464")
    corregido = preparar_desglose(
        expediente,
        indice=0,
        asignaciones=[("6537194", "300"), ("340464", "200")],
        motivo="Se distribuyó el importe conforme a vouchers individuales",
        confirmacion=True,
        version_esperada=0,
    )
    assert auditar_expedientes([corregido]) == ()
    assert corregido.datos_origen is None
    assert corregido.revisiones[0].cambios["referencia_original"] == (
        "6537194 Y 340464"
    )


def test_efectivo_reclasificado_sigue_en_revision_no_bancaria() -> None:
    antes = op("F001-26", "EFECTIVO?")
    corregido = preparar_reclasificacion_efectivo(
        antes,
        indice=0,
        motivo="El pago aún no cuenta con constancia bancaria",
        confirmacion=True,
        version_esperada=0,
    )
    hallazgos = auditar_expedientes([corregido])
    assert len(hallazgos) == 1
    assert hallazgos[0].tipo == "DECLARACIÓN DE PAGO POR ACLARAR"
    assert corregido.declaraciones_por_aclarar[0].importe_declarado == 500
    assert corregido.movimientos_bancarios == []

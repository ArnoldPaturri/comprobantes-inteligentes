"""Exportación financiera con filtros, importes exactos y textos seguros."""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from decimal import Decimal
from zipfile import ZipFile

from agente_comprobantes.control_financiero.modelos import (
    OperacionFlete,
    RevisionExpediente,
    SituacionControl,
)
from agente_comprobantes.control_financiero.presentacion import construir_tablero
from agente_comprobantes.control_financiero.reportes import exportar_control
from agente_comprobantes.control_financiero.repositorio_json import RepositorioControlFletes
from agente_comprobantes.dominio.enumeraciones import Moneda


def operacion(
    identificador: str,
    numero: str,
    monto: str,
    *,
    moneda: Moneda = Moneda.PEN,
    presupuesto: str | None = "100",
    cotizacion: str | None = "COT-1",
    es_flete: bool | None = True,
) -> OperacionFlete:
    return OperacionFlete(
        identificador=identificador,
        numero_factura=numero,
        moneda=moneda,
        monto_facturado=Decimal(monto),
        codigo_cotizacion=cotizacion,
        monto_cotizado=Decimal(presupuesto) if presupuesto is not None else None,
        es_flete=es_flete,
    )


def filas_csv(contenido: bytes, nombre: str) -> list[dict[str, str]]:
    with ZipFile(io.BytesIO(contenido)) as paquete:
        texto = paquete.read(nombre).decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(texto), delimiter=";"))


def test_zip_contiene_tablas_y_explicacion() -> None:
    data = exportar_control(construir_tablero([]))
    with ZipFile(io.BytesIO(data)) as z:
        assert set(z.namelist()) == {
            "operaciones.csv", "resumen_fletes.csv", "observaciones.csv",
            "historial.csv", "LEEME.txt",
        }
        assert z.read("operaciones.csv").startswith(b"\xef\xbb\xbf")
        assert b"resumen_fletes.csv" in z.read("LEEME.txt")


def test_operaciones_no_mezclan_monedas_y_presupuesto_no_se_duplica() -> None:
    op1 = operacion("FAC-1", "F001-1", "80")
    op2 = operacion("FAC-2", "F001-2", "45")
    op3 = operacion(
        "FAC-3", "F001-3", "20", moneda=Moneda.USD,
        cotizacion="COT-USD", presupuesto="15",
    )
    tablero = construir_tablero([op1, op2, op3])
    data = exportar_control(tablero)
    resumen = filas_csv(data, "resumen_fletes.csv")
    assert len(resumen) == 2
    pen = next(row for row in resumen if row["Moneda"] == "PEN")
    usd = next(row for row in resumen if row["Moneda"] == "USD")
    assert pen["Presupuesto identificado"] == "100.00"
    assert pen["Facturado con presupuesto"] == "125.00"
    assert pen["Exceso provisional"] == "25.00"
    assert usd["Exceso provisional"] == "5.00"
    assert len(filas_csv(data, "operaciones.csv")) == 3


def test_resumen_excluye_materiales_y_preserva_expediente() -> None:
    flete = operacion("FAC-1", "F001-1", "110")
    materiales = operacion(
        "FAC-2", "F001-2", "999", es_flete=False,
        cotizacion="COT-2", presupuesto="100",
    )
    data = exportar_control(construir_tablero([flete, materiales]))
    resumen = filas_csv(data, "resumen_fletes.csv")
    assert resumen[0]["Exceso provisional"] == "10.00"
    operaciones = filas_csv(data, "operaciones.csv")
    assert len(operaciones) == 2
    assert {fila["Clasificación"] for fila in operaciones} == {
        "Flete", "Otra operación",
    }


def test_operaciones_filtradas_pero_resumen_con_presupuesto_completo() -> None:
    uno = operacion("FAC-1", "F001-1", "80")
    dos = operacion("FAC-2", "F001-2", "45")
    tablero = construir_tablero([uno, dos])
    paquete = exportar_control(
        tablero, moneda=Moneda.PEN,
        situacion=SituacionControl.PENDIENTE, busqueda="F001-1",
    )
    assert [fila["ID expediente"] for fila in filas_csv(paquete, "operaciones.csv")] == [
        "FAC-1"
    ]
    assert filas_csv(paquete, "resumen_fletes.csv")[0][
        "Facturado con presupuesto"
    ] == "125.00"
    assert len(filas_csv(paquete, "observaciones.csv")) >= 1


def test_texto_no_se_ejecuta_como_formula_de_excel() -> None:
    op = operacion("FAC-1", "F001-1", "100")
    op = op.model_copy(update={"proveedor": "  =HYPERLINK(\"http://peligro\")"})
    op.revisiones.append(
        RevisionExpediente(
            fecha=datetime(2026, 10, 26, tzinfo=UTC),
            motivo="@SUM(1,2)",
            cambios={"cambio": "+CMD"},
        )
    )
    data = exportar_control(construir_tablero([op]))
    proveedor = filas_csv(data, "operaciones.csv")[0]["Proveedor"]
    assert proveedor.startswith("'  =")
    historial = filas_csv(data, "historial.csv")
    assert historial[0]["Motivo"] == "'@SUM(1,2)"
    assert historial[0]["Cambio"] == "'+CMD"


def test_lectura_y_exportacion_no_modifican_archivo_json(tmp_path) -> None:
    ruta = tmp_path / "control_fletes.json"
    repo = RepositorioControlFletes(ruta)
    repo.agregar(operacion("FAC-1", "F001-1", "200"))
    antes = ruta.read_bytes()
    data = exportar_control(construir_tablero(repo.listar()))
    assert filas_csv(data, "operaciones.csv")[0]["Facturado neto"] == "200.00"
    assert ruta.read_bytes() == antes


def test_historial_guarda_motivo_y_observaciones_separados() -> None:
    op = operacion("FAC-1", "F001-1", "100")
    op.revisiones.append(
        RevisionExpediente(
            fecha=datetime(2026, 10, 26, tzinfo=UTC),
            motivo="Control de factura y comprobante",
            cambios={"guia": "ninguna → EG-642"},
        )
    )
    paquete = exportar_control(construir_tablero([op]))
    historial = filas_csv(paquete, "historial.csv")
    observaciones = filas_csv(paquete, "observaciones.csv")
    assert len(historial) == 1
    assert historial[0]["Campo"] == "guia"
    assert historial[0]["Cambio"] == "ninguna → EG-642"
    assert any("guía" in row["Observación"] for row in observaciones)

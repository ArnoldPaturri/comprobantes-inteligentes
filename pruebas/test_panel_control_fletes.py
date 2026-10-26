"""El dashboard calcula importes sin mezclar divisas ni modificar archivos."""

from decimal import Decimal

from agente_comprobantes.control_financiero.modelos import (
    MovimientoBancario,
    OperacionFlete,
    SituacionControl,
)
from agente_comprobantes.control_financiero.presentacion import (
    cargar_tablero,
    construir_tablero,
    formatear_importe,
)
from agente_comprobantes.control_financiero.repositorio_json import RepositorioControlFletes
from agente_comprobantes.dominio.enumeraciones import Moneda


def operacion(
    identificador: str,
    moneda: Moneda,
    numero_factura: str,
    monto: str,
    proveedor: str,
) -> OperacionFlete:
    return OperacionFlete(
        identificador=identificador,
        moneda=moneda,
        numero_factura=numero_factura,
        monto_facturado=Decimal(monto),
        proveedor=proveedor,
        es_flete=True,
        movimientos_bancarios=[
            MovimientoBancario(
                importe_aplicado=Decimal("117.62"),
                moneda=moneda,
                referencia="OP-1",
                documento_respaldo="voucher.png",
                verificada=False,
            )
        ],
    )


def test_montos_declarados_no_son_montos_acreditados() -> None:
    objeto = operacion("FAC-1", Moneda.PEN, "F001-1", "30117.62", "Transportes")
    panel = construir_tablero([objeto])
    fila = panel.filas()[0]
    assert fila.declarado == Decimal("117.62")
    assert fila.acreditado == Decimal("0")
    assert fila.saldo_documental == Decimal("30117.62")
    assert fila.situacion == SituacionControl.PENDIENTE


def test_filtros_de_estado_moneda_y_busqueda() -> None:
    panel = construir_tablero([
        operacion("FAC-1", Moneda.PEN, "F001-1", "1000", "Empresa Andina"),
        operacion("FAC-2", Moneda.USD, "F002-1", "200", "Empresa Sur"),
    ])
    assert len(panel.filas(moneda=Moneda.PEN)) == 1
    assert len(panel.filas(situacion=SituacionControl.CONFORME)) == 0
    assert len(panel.filas(busqueda="ANDINA")) == 1
    assert len(panel.filas(busqueda="F002-1")) == 1
    assert len(panel.resumenes) == 2


def test_panel_lee_json_sin_alterarlo(tmp_path) -> None:
    ruta = tmp_path / "control_fletes.json"
    repositorio = RepositorioControlFletes(ruta)
    repositorio.agregar(
        operacion("FAC-1", Moneda.PEN, "F001-1", "1000", "Ejemplo")
    )
    antes = ruta.read_bytes()
    tablero = cargar_tablero(ruta)
    assert len(tablero.operaciones) == 1
    assert ruta.read_bytes() == antes


def test_panel_vacio_no_crea_archivo(tmp_path) -> None:
    ruta = tmp_path / "control_fletes.json"
    tablero = cargar_tablero(ruta)
    assert tablero.operaciones == []
    assert tablero.resumenes == []
    assert not ruta.exists()


def test_formato_monetario() -> None:
    assert formatear_importe(Decimal("30117.62"), Moneda.PEN) == "S/ 30,117.62"
    assert formatear_importe(Decimal("10"), Moneda.USD) == "US$ 10.00"

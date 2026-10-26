"""Reporte ejecutivo XLSX de consulta, separado del Excel de operaciones."""

from __future__ import annotations

from decimal import Decimal

from agente_comprobantes.control_financiero.libro_xlsx import (
    Formula,
    HojaReporte,
    crear_archivo_xlsx,
)
from agente_comprobantes.control_financiero.modelos import (
    OperacionFlete,
    SituacionControl,
)
from agente_comprobantes.control_financiero.presentacion import TableroFletes
from agente_comprobantes.dominio.enumeraciones import Moneda

CERO = Decimal("0")


def _operaciones(
    tablero: TableroFletes,
    filtradas: list[OperacionFlete],
) -> HojaReporte:
    filas: list[list[object]] = []
    for numero, op in enumerate(filtradas, 6):
        res = tablero.resultados[op.identificador]
        pagos_declarados = sum(
            (item.importe_aplicado for item in op.movimientos_bancarios), CERO
        )
        naturaleza = (
            "Sin clasificar" if op.es_flete is None
            else "Flete" if op.es_flete else "Otra operación"
        )
        filas.append([
            op.identificador,
            op.numero_factura,
            op.codigo_cotizacion or "",
            op.proveedor or "",
            op.moneda.value,
            naturaleza,
            op.numero_guia or "",
            op.fecha_factura.isoformat() if op.fecha_factura else "",
            res.facturado,
            res.notas_credito_acreditadas,
            Formula(
                f"I{numero}-J{numero}", res.facturado_neto,
            ),
            pagos_declarados,
            res.bancarizado_acreditado,
            res.detraccion_acreditada,
            Formula(
                f"M{numero}+N{numero}", res.total_acreditado,
            ),
            Formula(
                f"K{numero}-O{numero}", res.saldo_por_acreditar,
            ),
            res.situacion.value,
            len(res.observaciones),
        ])
    return HojaReporte(
        nombre="Operaciones",
        titulo="OPERACIONES · CONTROL DOCUMENTAL",
        subtitulo="Importes por factura. El saldo documental no indica necesariamente deuda.",
        encabezados=[
            "ID expediente", "Factura", "Cotización", "Proveedor", "Moneda",
            "Naturaleza", "Guía", "Fecha factura", "Facturado", "Notas crédito",
            "Facturado neto", "Pago declarado", "Pago acreditado", "Detracción",
            "Total acreditado", "Saldo documental", "Estado", "Observaciones",
        ],
        filas=filas,
        anchos=[19, 22, 21, 42, 12, 19, 20, 16, 18, 16, 18, 18, 18, 16, 19, 18, 17, 16],
        columnas_monetarias={9, 10, 11, 12, 13, 14, 15, 16},
    )


def _resumen(tablero: TableroFletes, moneda: Moneda | None) -> HojaReporte:
    filas: list[list[object]] = []
    for numero, r in enumerate(tablero.resumenes, 6):
        if moneda is not None and r.moneda != moneda:
            continue
        fila_excel = numero if moneda is None else 5 + len(filas) + 1
        filas.append([
            r.moneda.value,
            r.total_presupuestado,
            r.facturado_con_presupuesto,
            Formula(
                f"C{fila_excel}-B{fila_excel}",
                r.desviacion_neta_presupuestada,
            ),
            r.exceso_acumulado_presupuesto,
            r.facturado_sin_presupuesto,
            r.cantidad_conformes,
            r.cantidad_pendientes,
            r.cantidad_observadas,
            ", ".join(r.presupuestos_incompletos),
        ])
    return HojaReporte(
        nombre="Resumen ejecutivo",
        titulo="RESUMEN EJECUTIVO · COTIZACIONES Y FLETES",
        subtitulo=(
            "Solo fletes confirmados. Cotizaciones contadas una sola vez; "
            "exceso provisional, no sobrecosto aprobado."
        ),
        encabezados=[
            "Moneda", "Presupuesto", "Facturado c/presupuesto",
            "Desviación neta", "Exceso provisional", "Sin presupuesto",
            "Conformes", "Pendientes", "Observadas", "Cotizaciones incompletas",
        ],
        filas=filas,
        anchos=[12, 22, 25, 22, 22, 20, 14, 14, 14, 40],
        columnas_monetarias={2, 3, 4, 5, 6},
    )


def _observaciones(
    tablero: TableroFletes,
    filtradas: list[OperacionFlete],
) -> HojaReporte:
    filas = []
    for op in filtradas:
        res = tablero.resultados[op.identificador]
        for observacion in res.observaciones:
            filas.append([
                op.identificador, op.numero_factura,
                op.proveedor or "", op.moneda.value, res.situacion.value,
                observacion,
            ])
    return HojaReporte(
        nombre="Observaciones",
        titulo="OBSERVACIONES · OPERACIONES QUE REQUIEREN REVISIÓN",
        subtitulo="Cada fila corresponde a una observación de un expediente filtrado.",
        encabezados=[
            "ID expediente", "Factura", "Proveedor",
            "Moneda", "Estado", "Observación",
        ],
        filas=filas,
        anchos=[20, 22, 45, 13, 18, 100],
    )


def _historial(filtradas: list[OperacionFlete]) -> HojaReporte:
    filas = []
    for op in filtradas:
        for revision in op.revisiones:
            for campo, cambio in revision.cambios.items():
                filas.append([
                    op.identificador,
                    revision.fecha.isoformat(),
                    revision.motivo,
                    campo,
                    cambio,
                ])
    return HojaReporte(
        nombre="Historial",
        titulo="HISTORIAL LOCAL · REVISIONES DOCUMENTALES",
        subtitulo="Cambios declarados; sin identidad de usuario autenticada.",
        encabezados=["ID expediente", "Fecha UTC", "Motivo", "Campo", "Cambio"],
        filas=filas,
        anchos=[20, 28, 56, 30, 72],
    )


def _notas() -> HojaReporte:
    instrucciones = [
        ["Alcance", "Reporte de consulta. No modifica registros, adjuntos ni Excel original."],
        ["Resumen", "Solo fletes confirmados. No incluye compras u operaciones sin clasificar."],
        ["Filtros", "Operaciones, observaciones e historial respetan moneda, estado y búsqueda."],
        ["Presupuesto", "El resumen usa todas las facturas de cada cotización para evitar doble conteo."],
        ["Estado", "La conformidad es documental declarada, no confirmación bancaria."],
        ["Pago declarado", "Comprobante registrado u OCR, aunque aún no se haya acreditado."],
        ["Acreditado", "Evidencias con revisión documental registrada por el operador."],
        ["Saldo", "Monto sin acreditar documentalmente; no representa necesariamente deuda."],
        ["Exceso", "Estimación provisional del exceso frente al presupuesto."],
        ["Impuestos", "No se calcula ni confirma automáticamente la detracción ante SUNAT."],
        ["Monedas", "PEN, USD y otras divisas no se convierten ni suman entre sí."],
        ["Datos", "Montos numéricos con punto decimal, formato visual de dos decimales."],
        ["Seguridad", "Ningún texto OCR se inserta como fórmula ejecutable."],
    ]
    return HojaReporte(
        nombre="Leer primero",
        titulo="GUÍA DE INTERPRETACIÓN · COMPROBANTES INTELIGENTES",
        subtitulo="Indicadores, criterios de inclusión y límites de la información.",
        encabezados=["Concepto", "Descripción"],
        filas=instrucciones,
        anchos=[26, 105],
    )


def exportar_excel_ejecutivo(
    tablero: TableroFletes,
    *,
    moneda: Moneda | None = None,
    situacion: SituacionControl | None = None,
    busqueda: str = "",
) -> bytes:
    """Crea XLSX en memoria; no modifica las hojas Excel del agente."""
    ids = {fila.identificador for fila in tablero.filas(moneda, situacion, busqueda)}
    filtradas = [op for op in tablero.operaciones if op.identificador in ids]
    return crear_archivo_xlsx([
        _resumen(tablero, moneda),
        _operaciones(tablero, filtradas),
        _observaciones(tablero, filtradas),
        _historial(filtradas),
        _notas(),
    ])

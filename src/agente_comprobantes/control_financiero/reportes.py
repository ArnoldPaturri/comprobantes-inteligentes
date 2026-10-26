"""Reportes CSV de solo lectura compatibles con Excel.

Se exporta un ZIP con cuatro tablas separadas. No se recrea ni modifica
el libro operativo y no se ejecutan fórmulas suministradas en documentos.
"""

from __future__ import annotations

import csv
import io
from decimal import Decimal
from zipfile import ZIP_DEFLATED, ZipFile

from agente_comprobantes.control_financiero.modelos import (
    OperacionFlete,
    SituacionControl,
)
from agente_comprobantes.control_financiero.presentacion import TableroFletes
from agente_comprobantes.dominio.enumeraciones import Moneda

CERO = Decimal("0")


def _texto_seguro(valor: object) -> str:
    """Evita que Excel ejecute fórmulas contenidas en texto de OCR o usuarios."""
    texto = "" if valor is None else str(valor)
    texto = texto.replace("\x00", "")
    inicio = texto.lstrip("\ufeff \t\r\n")
    if inicio.startswith(("=", "+", "-", "@")) or texto.startswith(("\t", "\r", "\n")):
        return "'" + texto
    return texto


def _csv(soportes: list[str], filas: list[list[object]]) -> bytes:
    salida = io.StringIO(newline="")
    escritor = csv.writer(salida, delimiter=";", lineterminator="\r\n")
    escritor.writerow(soportes)
    for fila in filas:
        escritor.writerow(fila)
    return salida.getvalue().encode("utf-8-sig")


def _numero(importe: Decimal) -> str:
    """Se conserva valor decimal sin símbolos ni separador de miles."""
    return f"{importe:.2f}"


def _operaciones(tablero: TableroFletes, filtradas: list[OperacionFlete]) -> bytes:
    columnas = [
        "ID expediente", "N° factura", "Cotización", "Proveedor",
        "RUC", "Fecha factura", "Guía", "Moneda", "Clasificación",
        "Detracción aplica", "Estado", "Facturado", "Notas acreditadas",
        "Facturado neto", "Pago declarado", "Pago acreditado",
        "Detracción acreditada", "Total acreditado", "Saldo documental",
        "N° revisiones",
    ]
    filas = []
    for op in filtradas:
        res = tablero.resultados[op.identificador]
        declarado = sum(
            (m.importe_aplicado for m in op.movimientos_bancarios), CERO
        )
        if op.es_flete is None:
            clasificacion = "Sin clasificar"
        else:
            clasificacion = "Flete" if op.es_flete else "Otra operación"
        detraccion = (
            "Por determinar" if op.detraccion_aplica is None
            else "Sí" if op.detraccion_aplica else "No"
        )
        filas.append([
            _texto_seguro(op.identificador),
            _texto_seguro(op.numero_factura),
            _texto_seguro(op.codigo_cotizacion),
            _texto_seguro(op.proveedor),
            _texto_seguro(op.ruc_proveedor),
            op.fecha_factura.isoformat() if op.fecha_factura else "",
            _texto_seguro(op.numero_guia),
            op.moneda.value,
            clasificacion,
            detraccion,
            res.situacion.value,
            _numero(res.facturado),
            _numero(res.notas_credito_acreditadas),
            _numero(res.facturado_neto),
            _numero(declarado),
            _numero(res.bancarizado_acreditado),
            _numero(res.detraccion_acreditada),
            _numero(res.total_acreditado),
            _numero(res.saldo_por_acreditar),
            len(op.revisiones),
        ])
    return _csv(columnas, filas)


def _resumen(tablero: TableroFletes, moneda: Moneda | None) -> bytes:
    columnas = [
        "Moneda", "Presupuesto identificado", "Facturado con presupuesto",
        "Facturado sin presupuesto", "Desviación neta",
        "Exceso provisional", "Conformes", "Pendientes", "Observadas",
        "Operaciones sin presupuesto", "Cotizaciones incompletas",
    ]
    filas = []
    for r in tablero.resumenes:
        if moneda is not None and r.moneda != moneda:
            continue
        filas.append([
            r.moneda.value,
            _numero(r.total_presupuestado),
            _numero(r.facturado_con_presupuesto),
            _numero(r.facturado_sin_presupuesto),
            _numero(r.desviacion_neta_presupuestada),
            _numero(r.exceso_acumulado_presupuesto),
            r.cantidad_conformes,
            r.cantidad_pendientes,
            r.cantidad_observadas,
            r.cantidad_sin_presupuesto,
            _texto_seguro(", ".join(r.presupuestos_incompletos)),
        ])
    return _csv(columnas, filas)


def _observaciones(tablero: TableroFletes, filtradas: list[OperacionFlete]) -> bytes:
    columnas = [
        "ID expediente", "N° factura", "Proveedor", "Moneda",
        "Estado", "Observación",
    ]
    filas = []
    for op in filtradas:
        resultado = tablero.resultados[op.identificador]
        for observacion in resultado.observaciones:
            filas.append([
                _texto_seguro(op.identificador),
                _texto_seguro(op.numero_factura),
                _texto_seguro(op.proveedor),
                op.moneda.value,
                resultado.situacion.value,
                _texto_seguro(observacion),
            ])
    return _csv(columnas, filas)


def _historial(filtradas: list[OperacionFlete]) -> bytes:
    columnas = ["ID expediente", "Fecha UTC", "Motivo", "Campo", "Cambio"]
    filas = []
    for op in filtradas:
        for revision in op.revisiones:
            for campo, cambio in revision.cambios.items():
                filas.append([
                    _texto_seguro(op.identificador),
                    revision.fecha.isoformat(),
                    _texto_seguro(revision.motivo),
                    _texto_seguro(campo),
                    _texto_seguro(cambio),
                ])
    return _csv(columnas, filas)


def exportar_control(
    tablero: TableroFletes,
    *,
    moneda: Moneda | None = None,
    situacion: SituacionControl | None = None,
    busqueda: str = "",
) -> bytes:
    """Crea un ZIP en memoria; sin escritura en disco ni lectura de adjuntos.

    Operaciones, observaciones e historial respetan los filtros. El resumen
    incluye todos los fletes confirmados de las monedas seleccionadas, sin
    aplicar filtro de estado/búsqueda para no fraccionar presupuestos.
    """
    identificadores = {
        fila.identificador for fila in tablero.filas(moneda, situacion, busqueda)
    }
    filtradas = [
        op for op in tablero.operaciones if op.identificador in identificadores
    ]
    explicacion = (
        "COMPROBANTES INTELIGENTES — EXPORTACIÓN DE CONTROL FINANCIERO\n"
        "\n"
        "operaciones.csv: todos los expedientes que coinciden con los filtros.\n"
        "observaciones.csv: observaciones correspondientes a esos expedientes.\n"
        "historial.csv: revisiones locales de esos expedientes; sin identidad autenticada.\n"
        "resumen_fletes.csv: solo fletes confirmados, agrupados por moneda.\n"
        "El resumen respeta el filtro de moneda pero NO los filtros de estado\n"
        "ni búsqueda, para evitar sumar presupuestos parciales.\n"
        "\n"
        "Los importes son documentales; no equivalen a acreditación bancaria\n"
        "automática. El exceso es provisional, no un sobrecosto aprobado.\n"
        "El saldo documental no indica necesariamente deuda pendiente.\n"
        "Cada CSV utiliza UTF-8 con BOM, punto decimal y separador ';'.\n"
        "Ningún archivo modifica los Excel ni los JSON de origen.\n"
    )
    salida = io.BytesIO()
    with ZipFile(salida, mode="w", compression=ZIP_DEFLATED) as paquete:
        paquete.writestr("operaciones.csv", _operaciones(tablero, filtradas))
        paquete.writestr("resumen_fletes.csv", _resumen(tablero, moneda))
        paquete.writestr("observaciones.csv", _observaciones(tablero, filtradas))
        paquete.writestr("historial.csv", _historial(filtradas))
        paquete.writestr("LEEME.txt", explicacion.encode("utf-8"))
    return salida.getvalue()

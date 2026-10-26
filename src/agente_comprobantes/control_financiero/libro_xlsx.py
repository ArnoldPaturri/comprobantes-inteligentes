"""Escritura mínima de XLSX de consulta con librería estándar.

No importa ni modifica libros existentes. Genera documentos OOXML nuevos,
con texto literal (sin fórmulas procedentes de OCR ni archivos adjuntos).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"


def _q(etiqueta: str) -> str:
    return f"{{{NS}}}{etiqueta}"


def _elemento(nombre: str, attrs: dict[str, str] | None = None) -> ET.Element:
    return ET.Element(_q(nombre), attrs or {})


def _xml(raiz: ET.Element) -> bytes:
    return ET.tostring(raiz, encoding="utf-8", xml_declaration=True)


def _columna(numero: int) -> str:
    texto = ""
    while numero:
        numero, modulo = divmod(numero - 1, 26)
        texto = chr(65 + modulo) + texto
    return texto


def _texto(valor: object) -> str:
    texto = "" if valor is None else str(valor)
    # OOXML 1.0 no admite varios caracteres de control.
    return "".join(
        letra for letra in texto
        if ord(letra) >= 32 or letra in "\t\n\r"
    )


@dataclass(frozen=True)
class Formula:
    expresion: str
    resultado: Decimal


@dataclass
class HojaReporte:
    nombre: str
    titulo: str
    subtitulo: str
    encabezados: list[str]
    filas: list[list[object]]
    anchos: list[int]
    columnas_monetarias: set[int] = field(default_factory=set)


def _estilos() -> bytes:
    raiz = _elemento("styleSheet")
    formatos = ET.SubElement(raiz, _q("numFmts"), {"count": "1"})
    ET.SubElement(
        formatos, _q("numFmt"),
        {"numFmtId": "164", "formatCode": '#,##0.00;[Red](#,##0.00)'},
    )
    fuentes = ET.SubElement(raiz, _q("fonts"), {"count": "3"})
    for negrita, color, size in [
        (False, "243040", "11"),
        (True, "FFFFFF", "11"),
        (True, "FFFFFF", "17"),
    ]:
        font = ET.SubElement(fuentes, _q("font"))
        ET.SubElement(font, _q("sz"), {"val": size})
        ET.SubElement(font, _q("name"), {"val": "Aptos"})
        if negrita:
            ET.SubElement(font, _q("b"))
        ET.SubElement(font, _q("color"), {"rgb": "FF" + color})
    rellenos = ET.SubElement(raiz, _q("fills"), {"count": "5"})
    for color in [None, None, "714B67", "017E84", "FFF5DE"]:
        fill = ET.SubElement(rellenos, _q("fill"))
        if color:
            pat = ET.SubElement(fill, _q("patternFill"), {"patternType": "solid"})
            ET.SubElement(pat, _q("fgColor"), {"rgb": "FF" + color})
            ET.SubElement(pat, _q("bgColor"), {"indexed": "64"})
        else:
            ET.SubElement(
                fill, _q("patternFill"),
                {"patternType": "none" if color is None else "gray125"},
            )
    bordes = ET.SubElement(raiz, _q("borders"), {"count": "1"})
    borde = ET.SubElement(bordes, _q("border"))
    for lado in ["left", "right", "top", "bottom", "diagonal"]:
        ET.SubElement(borde, _q(lado))
    base = ET.SubElement(raiz, _q("cellStyleXfs"), {"count": "1"})
    ET.SubElement(base, _q("xf"), {"numFmtId": "0", "fontId": "0", "fillId": "0", "borderId": "0"})
    estilos = ET.SubElement(raiz, _q("cellXfs"), {"count": "6"})
    tipos = [
        ("0", "0", "0"),  # cuerpo
        ("1", "3", "0"),  # encabezado verde azulado
        ("2", "2", "0"),  # título
        ("0", "0", "164"),  # moneda
        ("0", "4", "0"),  # observación
        ("0", "4", "164"),  # cifra destacada
    ]
    for font, fill, formato in tipos:
        ET.SubElement(
            estilos, _q("xf"),
            {
                "numFmtId": formato,
                "fontId": font,
                "fillId": fill,
                "borderId": "0",
                "xfId": "0",
                "applyNumberFormat": "1",
                "applyAlignment": "1",
            },
        )
    ET.SubElement(raiz, _q("cellStyles"), {"count": "1"}).append(
        ET.Element(_q("cellStyle"), {"name": "Normal", "xfId": "0", "builtinId": "0"})
    )
    return _xml(raiz)


def _celda(fila: ET.Element, indice: int, numero: int, valor: object, estilo: int) -> None:
    celda = ET.SubElement(
        fila, _q("c"),
        {"r": f"{_columna(indice)}{numero}", "s": str(estilo)},
    )
    if isinstance(valor, Formula):
        ET.SubElement(celda, _q("f")).text = valor.expresion.removeprefix("=")
        ET.SubElement(celda, _q("v")).text = str(valor.resultado)
    elif isinstance(valor, (Decimal, int)) and not isinstance(valor, bool):
        ET.SubElement(celda, _q("v")).text = str(valor)
    elif valor is not None:
        celda.set("t", "inlineStr")
        inline = ET.SubElement(celda, _q("is"))
        texto = ET.SubElement(inline, _q("t"))
        texto.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        texto.text = _texto(valor)


def _hoja(info: HojaReporte) -> bytes:
    raiz = _elemento("worksheet")
    vistas = ET.SubElement(raiz, _q("sheetViews"))
    vista = ET.SubElement(vistas, _q("sheetView"), {"workbookViewId": "0"})
    ET.SubElement(
        vista, _q("pane"),
        {"ySplit": "5", "topLeftCell": "A6", "activePane": "bottomLeft", "state": "frozen"},
    )
    ET.SubElement(raiz, _q("sheetFormatPr"), {"defaultRowHeight": "18"})
    columnas = ET.SubElement(raiz, _q("cols"))
    for i, ancho in enumerate(info.anchos, 1):
        ET.SubElement(
            columnas, _q("col"),
            {"min": str(i), "max": str(i), "width": str(ancho), "customWidth": "1"},
        )
    datos = ET.SubElement(raiz, _q("sheetData"))
    encabezado = ET.SubElement(datos, _q("row"), {"r": "1", "ht": "32", "customHeight": "1"})
    _celda(encabezado, 1, 1, info.titulo, 2)
    subtitulo = ET.SubElement(datos, _q("row"), {"r": "2", "ht": "26", "customHeight": "1"})
    _celda(subtitulo, 1, 2, info.subtitulo, 0)
    cabecera = ET.SubElement(datos, _q("row"), {"r": "5", "ht": "32", "customHeight": "1"})
    for i, columna in enumerate(info.encabezados, 1):
        _celda(cabecera, i, 5, columna, 1)
    for indice, registro in enumerate(info.filas, 6):
        fila = ET.SubElement(datos, _q("row"), {"r": str(indice), "ht": "23", "customHeight": "1"})
        for i, valor in enumerate(registro, 1):
            estilo = 3 if i in info.columnas_monetarias else 0
            if valor in ("OBSERVADA", "PENDIENTE"):
                estilo = 4
            _celda(fila, i, indice, valor, estilo)
    maximo = _columna(len(info.encabezados))
    combinadas = ET.SubElement(raiz, _q("mergeCells"), {"count": "2"})
    for n in (1, 2):
        ET.SubElement(combinadas, _q("mergeCell"), {"ref": f"A{n}:{maximo}{n}"})
    ET.SubElement(
        raiz, _q("autoFilter"),
        {"ref": f"A5:{maximo}{max(6, 5 + len(info.filas))}"},
    )
    ET.SubElement(
        raiz, _q("pageMargins"),
        {"left": "0.3", "right": "0.3", "top": "0.6",
         "bottom": "0.6", "header": "0.2", "footer": "0.2"},
    )
    return _xml(raiz)


def crear_archivo_xlsx(hojas: list[HojaReporte]) -> bytes:
    """Genera un libro válido de consulta y evita escritura de archivos originales."""
    if not hojas or any(len(h.encabezados) != len(h.anchos) for h in hojas):
        raise ValueError("El reporte requiere hojas y encabezados bien definidos.")
    if len({h.nombre for h in hojas}) != len(hojas):
        raise ValueError("Los nombres de hojas deben ser únicos.")
    for hoja in hojas:
        if not hoja.nombre or len(hoja.nombre) > 31:
            raise ValueError("El nombre de hoja no es válido.")
        if any(len(fila) != len(hoja.encabezados) for fila in hoja.filas):
            raise ValueError("Las filas no coinciden con el número de columnas.")

    libro = _elemento("workbook")
    vistas = ET.SubElement(libro, _q("bookViews"))
    ET.SubElement(vistas, _q("workbookView"), {"activeTab": "0"})
    hojas_xml = ET.SubElement(libro, _q("sheets"))
    for i, hoja in enumerate(hojas, 1):
        ET.SubElement(
            hojas_xml, _q("sheet"),
            {"name": hoja.nombre, "sheetId": str(i), f"{{{REL}}}id": f"rId{i}"},
        )
    ET.SubElement(libro, _q("calcPr"), {"fullCalcOnLoad": "1"})

    relaciones = ET.Element(f"{{{PKG}}}Relationships")
    ET.SubElement(
        relaciones, f"{{{PKG}}}Relationship",
        {"Id": "rId1",
         "Type": f"{REL}/officeDocument", "Target": "xl/workbook.xml"},
    )
    libro_rels = ET.Element(f"{{{PKG}}}Relationships")
    for i in range(1, len(hojas) + 1):
        ET.SubElement(
            libro_rels, f"{{{PKG}}}Relationship",
            {"Id": f"rId{i}",
             "Type": f"{REL}/worksheet", "Target": f"worksheets/sheet{i}.xml"},
        )
    ET.SubElement(
        libro_rels, f"{{{PKG}}}Relationship",
        {"Id": "rIdStyles", "Type": f"{REL}/styles", "Target": "styles.xml"},
    )
    tipos = ET.Element(f"{{{TYPES}}}Types")
    ET.SubElement(
        tipos, f"{{{TYPES}}}Default",
        {"Extension": "rels",
         "ContentType": "application/vnd.openxmlformats-package.relationships+xml"},
    )
    ET.SubElement(
        tipos, f"{{{TYPES}}}Default",
        {"Extension": "xml", "ContentType": "application/xml"},
    )
    ET.SubElement(
        tipos, f"{{{TYPES}}}Override",
        {"PartName": "/xl/workbook.xml",
         "ContentType": (
             "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"
         )},
    )
    ET.SubElement(
        tipos, f"{{{TYPES}}}Override",
        {"PartName": "/xl/styles.xml",
         "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"},
    )
    for i in range(1, len(hojas) + 1):
        ET.SubElement(
            tipos, f"{{{TYPES}}}Override",
            {"PartName": f"/xl/worksheets/sheet{i}.xml",
             "ContentType": (
                 "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"
             )},
        )
    salida = BytesIO()
    with ZipFile(salida, "w", ZIP_DEFLATED) as paquete:
        paquete.writestr("[Content_Types].xml", _xml(tipos))
        paquete.writestr("_rels/.rels", _xml(relaciones))
        paquete.writestr("xl/workbook.xml", _xml(libro))
        paquete.writestr("xl/_rels/workbook.xml.rels", _xml(libro_rels))
        paquete.writestr("xl/styles.xml", _estilos())
        for i, hoja in enumerate(hojas, 1):
            paquete.writestr(f"xl/worksheets/sheet{i}.xml", _hoja(hoja))
    return salida.getvalue()

from __future__ import annotations

import os
import tempfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from agente_comprobantes.dominio import (
    EstadoCotizacion,
    EstadoPago,
)
from agente_comprobantes.excepciones import ErrorRepositorio
from agente_comprobantes.repositorios.conversion_filas_excel import ConversionFilasExcel
from agente_comprobantes.repositorios.esquemas_excel import ILLEGAL_EXCEL_CHARACTER_PATTERN


class UtilidadesExcel(ConversionFilasExcel):
    def leer_hoja(self, sheet_name: str) -> list[dict[str, object]]:
        if not self._path.exists():
            return []
        workbook = load_workbook(self._path, data_only=True, read_only=True)
        try:
            if sheet_name not in workbook.sheetnames:
                raise ErrorRepositorio(f"No existe la hoja {sheet_name}.")
            sheet = workbook[sheet_name]
            rows = sheet.iter_rows(values_only=True)
            headers = next(rows, None)
            if not headers:
                return []
            return [dict(zip(headers, row, strict=False)) for row in rows if any(row)]
        finally:
            workbook.close()

    @staticmethod
    def _inicializar_hoja(sheet: Any, headers: list[str]) -> None:
        sheet.append(headers)
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"
        fill = PatternFill("solid", fgColor="1F4E78")
        for cell in sheet[1]:
            cell.font = Font(color="FFFFFF", bold=True)
            cell.fill = fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
        for index, header in enumerate(headers, start=1):
            width = min(max(len(header) + 3, 14), 32)
            sheet.column_dimensions[get_column_letter(index)].width = width
        sheet.row_dimensions[1].height = 28

    @staticmethod
    def _verificar_encabezados(sheet: Any, expected: list[str]) -> bool:
        actual = [cell.value for cell in sheet[1]]

        while actual and actual[-1] is None:
            actual.pop()

        if actual == expected:
            return False

        if actual != expected[: len(actual)]:
            raise ErrorRepositorio(
                f"La hoja {sheet.title} existe, pero sus columnas "
                "no coinciden con el contrato."
            )

        fill = PatternFill("solid", fgColor="1F4E78")

        for index, header in enumerate(
            expected[len(actual):],
            start=len(actual) + 1,
        ):
            cell = sheet.cell(row=1, column=index, value=header)
            cell.font = Font(color="FFFFFF", bold=True)
            cell.fill = fill
            cell.alignment = Alignment(
                horizontal="center",
                vertical="center",
            )
            sheet.column_dimensions[get_column_letter(index)].width = min(
                max(len(header) + 3, 14),
                32,
            )

        sheet.auto_filter.ref = (
            f"A1:{get_column_letter(len(expected))}{sheet.max_row}"
        )
        return True

    @classmethod
    def _agregar_mapeo(cls, sheet: Any, headers: list[str], mapping: dict[str, Any]) -> None:
        sheet.append([cls._valor_excel(mapping.get(header)) for header in headers])
        row_number = sheet.max_row
        for cell in sheet[row_number]:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
        cls._aplicar_formatos_numericos(sheet, row_number, headers)
        sheet.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{sheet.max_row}"

    @staticmethod
    def _aplicar_formatos_numericos(sheet: Any, row_number: int, headers: list[str]) -> None:
        for index, header in enumerate(headers, start=1):
            cell = sheet.cell(row=row_number, column=index)
            if header.startswith("Monto") or header == "Diferencia ($)":
                cell.number_format = '#,##0.00;[Red]-#,##0.00'
            elif header == "% Desvío":
                cell.number_format = '0.0000;[Red]-0.0000'
            elif header.startswith("Fecha") and isinstance(cell.value, datetime):
                cell.number_format = "dd/mm/yyyy hh:mm"
            elif header.startswith("Fecha") and isinstance(cell.value, date):
                cell.number_format = "dd/mm/yyyy"

    @staticmethod
    def _valor_excel(value: Any) -> Any:
        if isinstance(value, Decimal):
            return float(value)

        if hasattr(value, "value"):
            value = value.value

        if isinstance(value, list):
            value = " | ".join(
                str(item)
                for item in value
            )

        if isinstance(value, str):
            return ILLEGAL_EXCEL_CHARACTER_PATTERN.sub(
                "",
                value,
            )

        return value

    @staticmethod
    def _actualizar_estado_cotizacion(sheet: Any, code: str, status: EstadoCotizacion) -> None:
        headers = {cell.value: cell.column for cell in sheet[1]}
        code_col = headers["Cód. Cotización"]
        status_col = headers["Estado"]
        for row_number in range(2, sheet.max_row + 1):
            current = sheet.cell(row=row_number, column=code_col).value
            if str(current).strip().upper() == code.strip().upper():
                sheet.cell(row=row_number, column=status_col).value = status.value
                return

    @staticmethod
    def _actualizar_estado_pago_factura(
        sheet: Any,
        invoice_id: str,
        status: EstadoPago,
    ) -> None:
        headers = {cell.value: cell.column for cell in sheet[1]}
        id_col = headers["ID Factura"]
        status_col = headers["Estado de Pago"]
        for row_number in range(2, sheet.max_row + 1):
            current = sheet.cell(row=row_number, column=id_col).value
            if str(current).strip().upper() == invoice_id.strip().upper():
                sheet.cell(row=row_number, column=status_col).value = status.value
                return

    @staticmethod
    def _actualizar_estado_pago_comparativa(
        sheet: Any,
        quotation_code: str,
        invoice_number: str | None,
        status: EstadoPago,
    ) -> None:
        headers = {cell.value: cell.column for cell in sheet[1]}
        quotation_col = headers["Cód. Cotización"]
        invoice_col = headers["N° Factura"]
        status_col = headers["Estado de Pago"]
        for row_number in range(2, sheet.max_row + 1):
            current_quotation = sheet.cell(row=row_number, column=quotation_col).value
            current_invoice = sheet.cell(row=row_number, column=invoice_col).value
            if (
                str(current_quotation).strip().upper() == quotation_code.strip().upper()
                and str(current_invoice or "").strip().upper()
                == str(invoice_number or "").strip().upper()
            ):
                sheet.cell(row=row_number, column=status_col).value = status.value
                return

    def _guardar_atomico(self, workbook: Any) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=self._path.parent, prefix=f".{self._path.stem}-", suffix=".xlsx", delete=False
            ) as temporary:
                temporary_path = Path(temporary.name)
            workbook.save(temporary_path)
            workbook.close()
            os.replace(temporary_path, self._path)
        except Exception as exc:
            workbook.close()
            if temporary_path and temporary_path.exists():
                temporary_path.unlink()
            raise ErrorRepositorio(f"No se pudo guardar el Excel: {self._path}") from exc

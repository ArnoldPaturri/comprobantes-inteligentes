from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook, Workbook

from invoice_agent.exceptions import RepositoryError
from invoice_agent.repositories.base import DocumentRepository
from invoice_agent.repositories.cotizaciones_excel import OperacionesCotizacionesExcel
from invoice_agent.repositories.esquemas_excel import SHEETS
from invoice_agent.repositories.facturas_excel import OperacionesFacturasExcel
from invoice_agent.repositories.pagos_excel import OperacionesPagosExcel
from invoice_agent.repositories.referencias_excel import ReferenciasExcel
from invoice_agent.repositories.utilidades_excel import UtilidadesExcel


class ExcelRepository(
    OperacionesCotizacionesExcel,
    OperacionesFacturasExcel,
    OperacionesPagosExcel,
    ReferenciasExcel,
    UtilidadesExcel,
    DocumentRepository,
):
    """Repositorio Excel compuesto por operaciones y utilidades especializadas."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path).expanduser().resolve()

    @property
    def location(self) -> str:
        return str(self._path)

    def initialize(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if self._path.exists():
            workbook = load_workbook(self._path)
            changed = False
            for name, headers in SHEETS.items():
                if name not in workbook.sheetnames:
                    sheet = workbook.create_sheet(name)
                    self._initialize_sheet(sheet, headers)
                    changed = True
                else:
                    changed = self._ensure_headers(workbook[name], headers) or changed
            if changed:
                self._save_atomic(workbook)
            else:
                workbook.close()
            return

        workbook = Workbook()
        default = workbook.active
        workbook.remove(default)
        for name, headers in SHEETS.items():
            sheet = workbook.create_sheet(name)
            self._initialize_sheet(sheet, headers)
        self._save_atomic(workbook)

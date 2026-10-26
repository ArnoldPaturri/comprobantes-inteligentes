from __future__ import annotations

from openpyxl import load_workbook

from agente_comprobantes.dominio import RegistroCotizacion
from agente_comprobantes.excepciones import ErrorCodigoDuplicado
from agente_comprobantes.repositorios.esquemas_excel import QUOTATION_HEADERS


class OperacionesCotizacionesExcel:
    def obtener_cotizacion(self, quotation_code: str) -> RegistroCotizacion | None:
        normalized = quotation_code.strip().upper()
        for row in self.leer_hoja("COTIZACIONES"):
            if str(row["Cód. Cotización"]).strip().upper() == normalized:
                return self._cotizacion_desde_fila(row)
        return None

    def listar_cotizaciones(self) -> list[RegistroCotizacion]:
        self.inicializar()

        quotations = [
            self._cotizacion_desde_fila(row)
            for row in self.leer_hoja("COTIZACIONES")
        ]

        return sorted(
            quotations,
            key=lambda quotation: quotation.registered_at,
            reverse=True,
        )

    def agregar_cotizacion(self, quotation: RegistroCotizacion) -> None:
        self.inicializar()
        if self.obtener_cotizacion(quotation.quotation_code):
            raise ErrorCodigoDuplicado(
                f"Ya existe la cotización {quotation.quotation_code}; no se creó otra fila."
            )

        workbook = load_workbook(self._path)
        sheet = workbook["COTIZACIONES"]
        self._agregar_mapeo(
            sheet,
            QUOTATION_HEADERS,
            {
                "Cód. Cotización": quotation.quotation_code,
                "Proveedor": quotation.provider,
                "RUC Proveedor": quotation.provider_tax_id,
                "Concepto / Descripción": quotation.concept,
                "Monto Cotizado": quotation.quoted_amount,
                "Moneda": quotation.currency,
                "Fecha Cotización": quotation.quotation_date,
                "Estado": quotation.status,
                "Estado Verificación": quotation.verification_status,
                "Hash Documento": quotation.source_hash,
                "Archivos Origen": quotation.source_files,
                "Campos Inciertos": quotation.uncertain_fields,
                "Fecha Registro": quotation.registered_at,
                "Acción / Observaciones": quotation.observations,
                
            },
        )
        self._guardar_atomico(workbook)

from __future__ import annotations

from pydantic import Field

from agente_comprobantes.dominio.conciliaciones import (
    ResultadoConciliacionPago,
    ResultadoConciliacion,
)
from agente_comprobantes.dominio.enumeraciones import (
    TipoDocumento,
    EstadoVinculacionPago,
    EstadoVerificacion,
)
from agente_comprobantes.dominio.modelo_base import ModeloDominio
from agente_comprobantes.dominio.referencias import CoincidenciaDuplicado
from agente_comprobantes.dominio.validacion import InformeValidacion


class ResultadoRegistro(ModeloDominio):
    document_id: str
    document_type: TipoDocumento
    verification_status: EstadoVerificacion
    workbook_path: str
    validation: InformeValidacion
    duplicates: list[CoincidenciaDuplicado] = Field(default_factory=list)
    reconciliation: ResultadoConciliacion | None = None
    payment_reconciliation: ResultadoConciliacionPago | None = None

class ResultadoVinculacionPago(ModeloDominio):
    payment_id: str
    invoice_id: str
    quotation_code: str
    reconciliation_status: EstadoVinculacionPago
    workbook_path: str
    payment_reconciliation: ResultadoConciliacionPago

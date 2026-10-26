from __future__ import annotations

from pydantic import Field

from agente_comprobantes.dominio.enumeraciones import Severidad
from agente_comprobantes.dominio.modelo_base import ModeloDominio


class ObservacionValidacion(ModeloDominio):
    code: str
    severity: Severidad
    field: str | None = None
    message: str

class InformeValidacion(ModeloDominio):
    issues: list[ObservacionValidacion] = Field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(issue.severity == Severidad.ERROR for issue in self.issues)

    @property
    def requires_review(self) -> bool:
        return bool(self.issues)

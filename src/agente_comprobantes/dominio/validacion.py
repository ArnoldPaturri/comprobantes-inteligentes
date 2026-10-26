from __future__ import annotations

from pydantic import Field

from agente_comprobantes.dominio.enumeraciones import Severity
from agente_comprobantes.dominio.modelo_base import DomainModel


class ValidationIssue(DomainModel):
    code: str
    severity: Severity
    field: str | None = None
    message: str

class ValidationReport(DomainModel):
    issues: list[ValidationIssue] = Field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(issue.severity == Severity.ERROR for issue in self.issues)

    @property
    def requires_review(self) -> bool:
        return bool(self.issues)

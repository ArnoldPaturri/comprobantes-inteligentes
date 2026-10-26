from agente_comprobantes.dominio import (
    CoincidenciaDuplicado,
    ResultadoConciliacionPago,
    ResultadoConciliacion,
    Severidad,
    InformeValidacion,
    EstadoVerificacion,
)


def resolve_verification_status(
    validation: InformeValidacion,
    duplicates: list[CoincidenciaDuplicado],
    reconciliation: ResultadoConciliacion | ResultadoConciliacionPago | None = None,
) -> EstadoVerificacion:
    issues = list(validation.issues)
    if reconciliation:
        issues.extend(reconciliation.issues)
    if any(issue.severity == Severidad.ERROR for issue in issues):
        return EstadoVerificacion.ERROR
    if duplicates:
        return EstadoVerificacion.POSSIBLE_DUPLICATE
    if issues:
        return EstadoVerificacion.REVIEW
    return EstadoVerificacion.VERIFIED


def issue_messages(
    validation: InformeValidacion,
    reconciliation: ResultadoConciliacion | ResultadoConciliacionPago | None = None,
) -> list[str]:
    messages = [issue.message for issue in validation.issues]
    if reconciliation:
        messages.extend(issue.message for issue in reconciliation.issues)
    return messages

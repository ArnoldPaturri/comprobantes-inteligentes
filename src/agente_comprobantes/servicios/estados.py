from invoice_agent.domain import (
    DuplicateMatch,
    PaymentReconciliationResult,
    ReconciliationResult,
    Severity,
    ValidationReport,
    VerificationStatus,
)


def resolve_verification_status(
    validation: ValidationReport,
    duplicates: list[DuplicateMatch],
    reconciliation: ReconciliationResult | PaymentReconciliationResult | None = None,
) -> VerificationStatus:
    issues = list(validation.issues)
    if reconciliation:
        issues.extend(reconciliation.issues)
    if any(issue.severity == Severity.ERROR for issue in issues):
        return VerificationStatus.ERROR
    if duplicates:
        return VerificationStatus.POSSIBLE_DUPLICATE
    if issues:
        return VerificationStatus.REVIEW
    return VerificationStatus.VERIFIED


def issue_messages(
    validation: ValidationReport,
    reconciliation: ReconciliationResult | PaymentReconciliationResult | None = None,
) -> list[str]:
    messages = [issue.message for issue in validation.issues]
    if reconciliation:
        messages.extend(issue.message for issue in reconciliation.issues)
    return messages

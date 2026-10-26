from decimal import ROUND_HALF_UP, Decimal
from difflib import SequenceMatcher

from invoice_agent.config import Settings
from invoice_agent.domain import (
    Diagnosis,
    DocumentExtraction,
    QuotationRecord,
    ReconciliationResult,
    Severity,
    ValidationIssue,
)
from invoice_agent.services.text_normalizer import normalize_supplier

MONEY_PLACES = Decimal("0.01")
PERCENT_PLACES = Decimal("0.0001")


class ReconciliationService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def compare(
        self,
        quotation: QuotationRecord,
        invoice: DocumentExtraction,
    ) -> ReconciliationResult:
        issues: list[ValidationIssue] = []
        provider_similarity = self._provider_similarity(quotation.provider, invoice.provider)

        if provider_similarity is None:
            issues.append(
                ValidationIssue(
                    code="SUPPLIER_NOT_COMPARABLE",
                    severity=Severity.WARNING,
                    field="provider",
                    message="No hay suficiente información para comparar proveedores.",
                )
            )
        elif provider_similarity < self._settings.supplier_similarity_threshold:
            issues.append(
                ValidationIssue(
                    code="SUPPLIER_MISMATCH",
                    severity=Severity.WARNING,
                    field="provider",
                    message=(
                        "El proveedor de la factura no coincide suficientemente con el de "
                        f"la cotización ({provider_similarity:.0%} de similitud)."
                    ),
                )
            )

        if quotation.currency and invoice.currency and quotation.currency != invoice.currency:
            issues.append(
                ValidationIssue(
                    code="CURRENCY_MISMATCH",
                    severity=Severity.ERROR,
                    field="currency",
                    message=(
                        f"Monedas diferentes: cotización {quotation.currency.value} y "
                        f"factura {invoice.currency.value}."
                    ),
                )
            )

        quoted = quotation.quoted_amount
        invoiced = invoice.total_amount
        if quoted is None or invoiced is None:
            return ReconciliationResult(
                quoted_amount=quoted,
                invoiced_amount=invoiced,
                difference=None,
                deviation_percent=None,
                diagnosis=Diagnosis.NOT_COMPARABLE,
                provider_similarity=provider_similarity,
                issues=issues,
            )

        difference = (invoiced - quoted).quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)
        if quoted == 0:
            deviation = None
            issues.append(
                ValidationIssue(
                    code="ZERO_QUOTED_AMOUNT",
                    severity=Severity.WARNING,
                    field="quoted_amount",
                    message="No se puede calcular el porcentaje porque el monto cotizado es cero.",
                )
            )
        else:
            deviation = ((difference / quoted) * 100).quantize(
                PERCENT_PLACES, rounding=ROUND_HALF_UP
            )

        if difference < 0:
            diagnosis = Diagnosis.BELOW
        elif difference > 0:
            diagnosis = Diagnosis.ABOVE
        else:
            diagnosis = Diagnosis.MATCH

        return ReconciliationResult(
            quoted_amount=quoted,
            invoiced_amount=invoiced,
            difference=difference,
            deviation_percent=deviation,
            diagnosis=diagnosis,
            provider_similarity=provider_similarity,
            issues=issues,
        )

    @staticmethod
    def _provider_similarity(left: str | None, right: str | None) -> float | None:
        normalized_left = normalize_supplier(left)
        normalized_right = normalize_supplier(right)
        if not normalized_left or not normalized_right:
            return None
        return SequenceMatcher(None, normalized_left, normalized_right).ratio()


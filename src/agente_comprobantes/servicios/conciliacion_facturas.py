from decimal import Decimal, ROUND_HALF_UP
from difflib import SequenceMatcher

from agente_comprobantes.configuracion import Configuracion
from agente_comprobantes.dominio import (
    Diagnostico,
    ExtraccionDocumento,
    ObservacionValidacion,
    RegistroCotizacion,
    ResultadoConciliacion,
    Severidad,
)
from agente_comprobantes.servicios.normalizacion_texto import normalize_supplier

MONEY_PLACES = Decimal("0.01")
PERCENT_PLACES = Decimal("0.0001")


class ServicioConciliacionFacturas:
    def __init__(self, settings: Configuracion) -> None:
        self._settings = settings

    def compare(
        self,
        quotation: RegistroCotizacion,
        invoice: ExtraccionDocumento,
    ) -> ResultadoConciliacion:
        issues: list[ObservacionValidacion] = []
        provider_similarity = self._provider_similarity(quotation.provider, invoice.provider)

        if provider_similarity is None:
            issues.append(
                ObservacionValidacion(
                    code="SUPPLIER_NOT_COMPARABLE",
                    severity=Severidad.WARNING,
                    field="provider",
                    message="No hay suficiente información para comparar proveedores.",
                )
            )
        elif provider_similarity < self._settings.supplier_similarity_threshold:
            issues.append(
                ObservacionValidacion(
                    code="SUPPLIER_MISMATCH",
                    severity=Severidad.WARNING,
                    field="provider",
                    message=(
                        "El proveedor de la factura no coincide suficientemente con el de "
                        f"la cotización ({provider_similarity:.0%} de similitud)."
                    ),
                )
            )

        if quotation.currency and invoice.currency and quotation.currency != invoice.currency:
            issues.append(
                ObservacionValidacion(
                    code="CURRENCY_MISMATCH",
                    severity=Severidad.ERROR,
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
            return ResultadoConciliacion(
                quoted_amount=quoted,
                invoiced_amount=invoiced,
                difference=None,
                deviation_percent=None,
                diagnosis=Diagnostico.NOT_COMPARABLE,
                provider_similarity=provider_similarity,
                issues=issues,
            )

        difference = (invoiced - quoted).quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)
        if quoted == 0:
            deviation = None
            issues.append(
                ObservacionValidacion(
                    code="ZERO_QUOTED_AMOUNT",
                    severity=Severidad.WARNING,
                    field="quoted_amount",
                    message="No se puede calcular el porcentaje porque el monto cotizado es cero.",
                )
            )
        else:
            deviation = ((difference / quoted) * 100).quantize(
                PERCENT_PLACES, rounding=ROUND_HALF_UP
            )

        if difference < 0:
            diagnosis = Diagnostico.BELOW
        elif difference > 0:
            diagnosis = Diagnostico.ABOVE
        else:
            diagnosis = Diagnostico.MATCH

        return ResultadoConciliacion(
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


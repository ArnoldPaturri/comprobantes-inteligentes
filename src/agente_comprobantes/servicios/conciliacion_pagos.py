from decimal import ROUND_HALF_UP, Decimal

from agente_comprobantes.dominio import (
    EstadoPago,
    ExtraccionDocumento,
    ObservacionValidacion,
    RegistroFactura,
    ResultadoConciliacionPago,
    Severidad,
)

MONEY_PLACES = Decimal("0.01")
PERCENT_PLACES = Decimal("0.01")
DEFAULT_MIN_PAYMENT_RATIO = Decimal("0.10")

class ServicioConciliacionPagos:
    """Compara pagos acumulados con una factura sin usar el modelo de IA."""

    def __init__(
        self,
        min_payment_ratio: Decimal = DEFAULT_MIN_PAYMENT_RATIO,
    ) -> None:
        if not Decimal("0") <= min_payment_ratio < Decimal("1"):
            raise ValueError(
                "min_payment_ratio debe estar entre 0 y 1."
            )

        self._min_payment_ratio = min_payment_ratio

    def comparar(
        self,
        invoice: RegistroFactura,
        payment: ExtraccionDocumento,
        previously_paid: Decimal = Decimal("0"),
        apply_payment: bool = True,
    ) -> ResultadoConciliacionPago:
        issues: list[ObservacionValidacion] = []
        invoice_amount = invoice.invoiced_amount
        payment_amount = payment.total_amount

        if invoice.currency and payment.currency and invoice.currency != payment.currency:
            issues.append(
                ObservacionValidacion(
                    code="PAYMENT_CURRENCY_MISMATCH",
                    severity=Severidad.ERROR,
                    field="currency",
                    message=(
                        f"Monedas diferentes: factura {invoice.currency.value} y "
                        f"pago {payment.currency.value}."
                    ),
                )
            )

        if invoice_amount is None or payment_amount is None:
            return ResultadoConciliacionPago(
                invoice_amount=invoice_amount,
                previously_paid_amount=previously_paid,
                current_payment_amount=payment_amount,
                applied_amount=Decimal("0"),
                accumulated_paid_amount=previously_paid,
                remaining_amount=None,
                resulting_payment_status=invoice.payment_status,
                applied=False,
                issues=issues,
            )
        if not apply_payment:
            remaining = (invoice_amount - previously_paid).quantize(
                MONEY_PLACES,
                rounding=ROUND_HALF_UP,
            )
            return ResultadoConciliacionPago(
                invoice_amount=invoice_amount,
                previously_paid_amount=previously_paid,
                current_payment_amount=payment_amount,
                applied_amount=Decimal("0"),
                accumulated_paid_amount=previously_paid,
                remaining_amount=remaining,
                resulting_payment_status=invoice.payment_status,
                applied=False,
                issues=issues,
            )
            
        outstanding_amount = (
            invoice_amount - previously_paid
        ).quantize(
            MONEY_PLACES,
            rounding=ROUND_HALF_UP,
        )

        if (
            outstanding_amount > 0
            and payment_amount > 0
            and payment_amount < outstanding_amount
        ):
            payment_ratio = payment_amount / outstanding_amount

            if payment_ratio < self._min_payment_ratio:
                payment_percentage = (
                    payment_ratio * Decimal("100")
                ).quantize(
                    PERCENT_PLACES,
                    rounding=ROUND_HALF_UP,
                )

                issues.append(
                    ObservacionValidacion(
                        code="PAYMENT_AMOUNT_SUSPICIOUSLY_LOW",
                        severity=Severidad.WARNING,
                        field="total_amount",
                        message=(
                            f"El pago representa solo "
                            f"{payment_percentage:.2f}% del saldo "
                            f"pendiente ({outstanding_amount:.2f}). "
                            "Confirma el monto antes de aplicarlo."
                        ),
                    )
                )
        accumulated = (previously_paid + payment_amount).quantize(
            MONEY_PLACES, rounding=ROUND_HALF_UP
        )
        remaining = (invoice_amount - accumulated).quantize(
            MONEY_PLACES, rounding=ROUND_HALF_UP
        )

        if remaining < 0:
            issues.append(
                ObservacionValidacion(
                    code="PAYMENT_EXCEEDS_INVOICE",
                    severity=Severidad.WARNING,
                    field="total_amount",
                    message=(
                        "El pago acumulado excedería el monto facturado por "
                        f"{abs(remaining):.2f}."
                    ),
                )
            )
            resulting_status = EstadoPago.REVIEW
        elif remaining == 0:
            resulting_status = EstadoPago.PAID
        else:
            resulting_status = EstadoPago.PARTIALLY_PAID

        return ResultadoConciliacionPago(
            invoice_amount=invoice_amount,
            previously_paid_amount=previously_paid,
            current_payment_amount=payment_amount,
            applied_amount=payment_amount,
            accumulated_paid_amount=accumulated,
            remaining_amount=remaining,
            resulting_payment_status=resulting_status,
            applied=True,
            issues=issues,
        )

    @staticmethod
    def rechazar_aplicacion(
        reconciliation: ResultadoConciliacionPago,
        current_status: EstadoPago,
    ) -> ResultadoConciliacionPago:
        """Conserva la trazabilidad, pero evita aplicar pagos dudosos o duplicados."""

        invoice_amount = reconciliation.invoice_amount
        previously_paid = reconciliation.previously_paid_amount
        remaining = (
            None
            if invoice_amount is None
            else (invoice_amount - previously_paid).quantize(
                MONEY_PLACES, rounding=ROUND_HALF_UP
            )
        )
        return reconciliation.model_copy(
            update={
                "applied_amount": Decimal("0"),
                "accumulated_paid_amount": previously_paid,
                "remaining_amount": remaining,
                "resulting_payment_status": current_status,
                "applied": False,
            }
        )

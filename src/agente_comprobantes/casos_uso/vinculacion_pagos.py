from __future__ import annotations

from agente_comprobantes.dominio import (
    EstadoVerificacion,
    EstadoVinculacionPago,
    ExtraccionDocumento,
    ResultadoVinculacionPago,
)
from agente_comprobantes.excepciones import ErrorEstadoRegistro, ErrorRegistroNoEncontrado


class OperacionesVinculacionPagos:
    """Vinculación de pagos pendientes con facturas registradas."""

    def vincular_pago(
        self,
        payment_id: str,
        invoice_id: str,
    ) -> ResultadoVinculacionPago:
        self._repository.inicializar()

        payment = self._repository.obtener_pago(payment_id)
        if payment is None:
            raise ErrorRegistroNoEncontrado(
                f"No existe el pago "
                f"{payment_id.strip().upper()}."
            )

        invoice = self._repository.obtener_factura(invoice_id)
        if invoice is None:
            raise ErrorRegistroNoEncontrado(
                f"No existe la factura "
                f"{invoice_id.strip().upper()}."
            )

        if (
            payment.verification_status
            != EstadoVerificacion.VERIFIED
        ):
            raise ErrorEstadoRegistro(
                f"El pago {payment.payment_id} tiene estado "
                f"{payment.verification_status.value} "
                "y no puede conciliarse."
            )

        if (
            payment.reconciliation_status
            != EstadoVinculacionPago.PENDING_INVOICE
        ):
            raise ErrorEstadoRegistro(
                f"El pago {payment.payment_id} tiene estado "
                f"de conciliación "
                f"{payment.reconciliation_status.value}."
            )

        if invoice.verification_status in {
            EstadoVerificacion.POSSIBLE_DUPLICATE,
            EstadoVerificacion.ERROR,
        }:
            raise ErrorEstadoRegistro(
                f"La factura {invoice.invoice_id} tiene estado "
                f"{invoice.verification_status.value} "
                "y no puede recibir pagos."
            )

        if payment.quotation_code != invoice.quotation_code:
            raise ErrorEstadoRegistro(
                f"El pago {payment.payment_id} y la factura "
                f"{invoice.invoice_id} pertenecen a "
                "cotizaciones diferentes."
            )

        extraction = ExtraccionDocumento(
            document_type=payment.payment_type,
            document_date=payment.payment_date,
            total_amount=payment.paid_amount,
            currency=payment.currency,
            operation_number=payment.operation_number,
            payment_entity=payment.payment_entity,
            confidence=1,
        )

        previously_paid = (
            self._repository.obtener_total_pagos_verificados(
                invoice.invoice_id
            )
        )

        reconciliation = self._payment_reconciliation.comparar(
            invoice,
            extraction,
            previously_paid,
        )

        applied = not reconciliation.issues

        if not applied:
            reconciliation = (
                self._payment_reconciliation.rechazar_aplicacion(
                    reconciliation,
                    invoice.payment_status,
                )
            )

        reconciliation_status = (
            EstadoVinculacionPago.RECONCILED
            if applied
            else EstadoVinculacionPago.REVIEW
        )

        observations = [
            *payment.observations,
            *(
                issue.message
                for issue in reconciliation.issues
            ),
            (
                f"Pago vinculado a la factura "
                f"{invoice.invoice_id}."
                if applied
                else (
                    "No se pudo vincular automáticamente a "
                    f"{invoice.invoice_id}."
                )
            ),
        ]

        updated_payment = payment.model_copy(
            update={
                "invoice_id": (
                    invoice.invoice_id
                    if applied
                    else None
                ),
                "reconciliation_status": (
                    reconciliation_status
                ),
                "observations": self._unique(observations),
            }
        )

        self._repository.vincular_pago(
            updated_payment,
            invoice,
            reconciliation,
        )

        return ResultadoVinculacionPago(
            payment_id=payment.payment_id,
            invoice_id=invoice.invoice_id,
            quotation_code=payment.quotation_code,
            reconciliation_status=reconciliation_status,
            workbook_path=self._repository.ubicacion,
            payment_reconciliation=reconciliation,
        )

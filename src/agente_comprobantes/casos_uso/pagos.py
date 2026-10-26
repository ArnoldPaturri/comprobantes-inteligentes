from __future__ import annotations

from uuid import uuid4

from agente_comprobantes.dominio import (
    EstadoVerificacion,
    EstadoVinculacionPago,
    ExtraccionDocumento,
    RegistroPago,
    ResultadoRegistro,
    TipoDocumento,
)
from agente_comprobantes.excepciones import ErrorEstadoRegistro, ErrorRegistroNoEncontrado
from agente_comprobantes.servicios.estados import mensajes_observaciones, resolver_estado_verificacion


class OperacionesPagos:
    def registrar_pago(
        self,
        quotation_code: str,
        image_paths: list[str],
        invoice_id: str | None = None,
        *,
        confirmed_extraction: ExtraccionDocumento | None = None,
    ) -> ResultadoRegistro:
        self._repository.inicializar()

        quotation = self._repository.obtener_cotizacion(quotation_code)
        if quotation is None:
            raise ErrorRegistroNoEncontrado(
                f"No existe la cotización "
                f"{quotation_code.strip().upper()}. "
                "Regístrala antes de procesar el pago."
            )

        invoice = None

        if invoice_id:
            invoice = self._repository.obtener_factura(invoice_id)

            if invoice is None:
                raise ErrorRegistroNoEncontrado(
                    f"No existe la factura {invoice_id.strip().upper()}."
                )

            if invoice.quotation_code != quotation.quotation_code:
                raise ErrorEstadoRegistro(
                    f"La factura {invoice.invoice_id} no pertenece a "
                    f"la cotización {quotation.quotation_code}."
                )

            if invoice.verification_status in {
                EstadoVerificacion.POSSIBLE_DUPLICATE,
                EstadoVerificacion.ERROR,
            }:
                raise ErrorEstadoRegistro(
                    f"La factura {invoice.invoice_id} tiene estado "
                    f"{invoice.verification_status.value} y no puede "
                    "recibir pagos."
                )

        prepared = self._images.preparar(image_paths)
        extraction = (
            confirmed_extraction
            if confirmed_extraction is not None
            else self._provider.extraer(
                prepared,
                TipoDocumento.PAYMENT_RECEIPT,
            )
        )
        validation = self._validator.validar_pago(extraction)

        duplicates = self._duplicates.buscar_coincidencias(
            extraction,
            prepared.source_hash,
            self._repository.listar_referencias_documentos(),
        )

        payment_reconciliation = None

        if invoice is not None:
            previously_paid = (
                self._repository.obtener_total_pagos_verificados(
                    invoice.invoice_id
                )
            )

            payment_reconciliation = (
                self._payment_reconciliation.comparar(
                    invoice,
                    extraction,
                    previously_paid,
                    apply_payment=not duplicates,
                )
            )

            status = resolver_estado_verificacion(
                validation,
                duplicates,
                payment_reconciliation,
            )

            if (
                status != EstadoVerificacion.VERIFIED
                and payment_reconciliation.applied
            ):
                payment_reconciliation = (
                    self._payment_reconciliation.rechazar_aplicacion(
                        payment_reconciliation,
                        invoice.payment_status,
                    )
                )

            reconciliation_status = (
                EstadoVinculacionPago.RECONCILED
                if payment_reconciliation.applied
                else EstadoVinculacionPago.REVIEW
            )
        else:
            status = resolver_estado_verificacion(
                validation,
                duplicates,
            )

            reconciliation_status = (
                EstadoVinculacionPago.PENDING_INVOICE
                if status == EstadoVerificacion.VERIFIED
                else EstadoVinculacionPago.REVIEW
            )

        observations = [
            *extraction.observations,
            *mensajes_observaciones(
                validation,
                payment_reconciliation,
            ),
        ]

        if duplicates:
            observations.append(
                "Posible coincidencia con: "
                + ", ".join(
                    match.document_id
                    for match in duplicates[:3]
                )
            )

        if invoice is None:
            observations.append(
                "Pago registrado y pendiente de factura."
            )
        else:
            observations.append(
                "Pago aplicado a la factura."
                if (
                    payment_reconciliation
                    and payment_reconciliation.applied
                )
                else "Pago registrado, pero no aplicado a la factura."
            )

        payment_id = f"PAG-{uuid4().hex[:10].upper()}"

        record = RegistroPago(
            payment_id=payment_id,
            quotation_code=quotation.quotation_code,
            invoice_id=invoice.invoice_id if invoice else None,
            payment_type=extraction.document_type,
            payment_entity=extraction.payment_entity,
            operation_number=extraction.operation_number,
            paid_amount=extraction.total_amount,
            currency=extraction.currency,
            payment_date=extraction.document_date,
            verification_status=status,
            reconciliation_status=reconciliation_status,
            source_hash=prepared.source_hash,
            source_files=prepared.nombres_archivos,
            duplicate_of=[
                match.document_id
                for match in duplicates
            ],
            observations=self._unique(observations),
        )

        self._repository.agregar_pago(
            record,
            invoice,
            payment_reconciliation,
        )

        return ResultadoRegistro(
            document_id=payment_id,
            document_type=extraction.document_type,
            verification_status=status,
            workbook_path=self._repository.ubicacion,
            validation=validation,
            duplicates=duplicates,
            payment_reconciliation=payment_reconciliation,
        )

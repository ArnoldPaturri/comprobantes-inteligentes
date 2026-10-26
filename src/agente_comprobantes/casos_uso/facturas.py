from __future__ import annotations

from uuid import uuid4

from agente_comprobantes.dominio import (
    ExtraccionDocumento,
    TipoDocumento,
    RegistroFactura,
    EstadoPago,
    ResultadoRegistro,
)
from agente_comprobantes.excepciones import ErrorRegistroNoEncontrado
from agente_comprobantes.servicios.estados import issue_messages, resolve_verification_status


class OperacionesFacturas:
    def register_invoice(
        self,
        quotation_code: str,
        image_paths: list[str],
        *,
        confirmed_extraction: ExtraccionDocumento | None = None,
    ) -> ResultadoRegistro:
        self._repository.initialize()
        quotation = self._repository.get_quotation(quotation_code)
        if quotation is None:
            raise ErrorRegistroNoEncontrado(
                f"No existe la cotización {quotation_code.strip().upper()}. "
                "Regístrala antes de procesar la factura."
            )

        prepared = self._images.prepare(image_paths)
        extraction = (
            confirmed_extraction
            if confirmed_extraction is not None
            else self._provider.extract(
                prepared,
                TipoDocumento.INVOICE,
            )
        )
        validation = self._validator.validate(extraction, TipoDocumento.INVOICE)
        duplicates = self._duplicates.find_matches(
            extraction, prepared.source_hash, self._repository.list_document_references()
        )
        reconciliation = self._reconciliation.compare(quotation, extraction)
        status = resolve_verification_status(validation, duplicates, reconciliation)
        observations = [
            *extraction.observations,
            *issue_messages(validation, reconciliation),
        ]
        if duplicates:
            observations.append(
                "Posible coincidencia con: "
                + ", ".join(match.document_id for match in duplicates[:3])
            )

        invoice_id = f"FAC-{uuid4().hex[:10].upper()}"
        record = RegistroFactura(
            invoice_id=invoice_id,
            quotation_code=quotation.quotation_code,
            provider=extraction.provider,
            provider_tax_id=extraction.provider_tax_id,
            invoice_number=extraction.document_number,
            concept=extraction.concept,
            invoiced_amount=extraction.total_amount,
            currency=extraction.currency,
            invoice_date=extraction.document_date,
            verification_status=status,
            payment_status=EstadoPago.PENDING,
            source_hash=prepared.source_hash,
            source_files=prepared.source_names,
            uncertain_fields=extraction.uncertain_fields,
            duplicate_of=[match.document_id for match in duplicates],
            observations=self._unique(observations),
        )
        self._repository.add_invoice(record, quotation, reconciliation)
        return ResultadoRegistro(
            document_id=invoice_id,
            document_type=TipoDocumento.INVOICE,
            verification_status=status,
            workbook_path=self._repository.location,
            validation=validation,
            duplicates=duplicates,
            reconciliation=reconciliation,
        )

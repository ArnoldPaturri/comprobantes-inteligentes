from __future__ import annotations

from uuid import uuid4

from invoice_agent.domain import (
    DocumentExtraction,
    DocumentType,
    InvoiceRecord,
    PaymentLinkResult,
    PaymentLinkStatus,
    PaymentRecord,
    PaymentStatus,
    QuotationRecord,
    QuotationStatus,
    RegistrationResult,
    VerificationStatus,
)
from invoice_agent.exceptions import InvalidRecordStateError, RecordNotFoundError
from invoice_agent.providers.base import VisionProvider
from invoice_agent.repositories.base import DocumentRepository
from invoice_agent.services.duplicate_service import DuplicateService
from invoice_agent.services.image_service import ImageService
from invoice_agent.services.payment_reconciliation_service import PaymentReconciliationService
from invoice_agent.services.reconciliation_service import ReconciliationService
from invoice_agent.services.status_service import issue_messages, resolve_verification_status
from invoice_agent.services.validation_service import ValidationService


class ReceiptAgent:
    """Caso de uso principal; no depende de Streamlit ni de un proveedor concreto."""

    def __init__(
        self,
        provider: VisionProvider,
        repository: DocumentRepository,
        image_service: ImageService,
        validation_service: ValidationService,
        duplicate_service: DuplicateService,
        reconciliation_service: ReconciliationService,
        payment_reconciliation_service: PaymentReconciliationService,
    ) -> None:
        self._provider = provider
        self._repository = repository
        self._images = image_service
        self._validator = validation_service
        self._duplicates = duplicate_service
        self._reconciliation = reconciliation_service
        self._payment_reconciliation = payment_reconciliation_service

    def preview_extraction(
        self,
        expected_type: DocumentType,
        image_paths: list[str],
    ) -> DocumentExtraction:
        """Extrae un documento sin validar, conciliar ni guardar registros."""
        prepared = self._images.prepare(image_paths)
        return self._provider.extract(
            prepared,
            expected_type,
        )

    def register_quotation(
        self,
        quotation_code: str,
        image_paths: list[str],
        *,
        confirmed_extraction: DocumentExtraction | None = None,
    ) -> RegistrationResult:
        self._repository.initialize()
        prepared = self._images.prepare(image_paths)
        extraction = (
            confirmed_extraction
            if confirmed_extraction is not None
            else self._provider.extract(
                prepared,
                DocumentType.QUOTATION,
            )
        )
        validation = self._validator.validate(extraction, DocumentType.QUOTATION)
        duplicates = self._duplicates.find_matches(
            extraction, prepared.source_hash, self._repository.list_document_references()
        )
        status = resolve_verification_status(validation, duplicates)
        observations = [*extraction.observations, *issue_messages(validation)]
        if duplicates:
            observations.append(
                "Posible coincidencia con: "
                + ", ".join(match.document_id for match in duplicates[:3])
            )

        record = QuotationRecord(
            quotation_code=quotation_code,
            provider=extraction.provider,
            provider_tax_id=extraction.provider_tax_id,
            concept=extraction.concept,
            quoted_amount=extraction.total_amount,
            currency=extraction.currency,
            quotation_date=extraction.document_date,
            status=QuotationStatus.WAITING_INVOICE,
            verification_status=status,
            source_hash=prepared.source_hash,
            source_files=prepared.source_names,
            uncertain_fields=extraction.uncertain_fields,
            observations=self._unique(observations),
        )
        self._repository.add_quotation(record)
        return RegistrationResult(
            document_id=record.quotation_code,
            document_type=DocumentType.QUOTATION,
            verification_status=status,
            workbook_path=self._repository.location,
            validation=validation,
            duplicates=duplicates,
        )

    def register_invoice(
        self,
        quotation_code: str,
        image_paths: list[str],
        *,
        confirmed_extraction: DocumentExtraction | None = None,
    ) -> RegistrationResult:
        self._repository.initialize()
        quotation = self._repository.get_quotation(quotation_code)
        if quotation is None:
            raise RecordNotFoundError(
                f"No existe la cotización {quotation_code.strip().upper()}. "
                "Regístrala antes de procesar la factura."
            )

        prepared = self._images.prepare(image_paths)
        extraction = (
            confirmed_extraction
            if confirmed_extraction is not None
            else self._provider.extract(
                prepared,
                DocumentType.INVOICE,
            )
        )
        validation = self._validator.validate(extraction, DocumentType.INVOICE)
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
        record = InvoiceRecord(
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
            payment_status=PaymentStatus.PENDING,
            source_hash=prepared.source_hash,
            source_files=prepared.source_names,
            uncertain_fields=extraction.uncertain_fields,
            duplicate_of=[match.document_id for match in duplicates],
            observations=self._unique(observations),
        )
        self._repository.add_invoice(record, quotation, reconciliation)
        return RegistrationResult(
            document_id=invoice_id,
            document_type=DocumentType.INVOICE,
            verification_status=status,
            workbook_path=self._repository.location,
            validation=validation,
            duplicates=duplicates,
            reconciliation=reconciliation,
        )

    def register_payment(
        self,
        quotation_code: str,
        image_paths: list[str],
        invoice_id: str | None = None,
        *,
        confirmed_extraction: DocumentExtraction | None = None,
    ) -> RegistrationResult:
        self._repository.initialize()

        quotation = self._repository.get_quotation(quotation_code)
        if quotation is None:
            raise RecordNotFoundError(
                f"No existe la cotización "
                f"{quotation_code.strip().upper()}. "
                "Regístrala antes de procesar el pago."
            )

        invoice = None

        if invoice_id:
            invoice = self._repository.get_invoice(invoice_id)

            if invoice is None:
                raise RecordNotFoundError(
                    f"No existe la factura {invoice_id.strip().upper()}."
                )

            if invoice.quotation_code != quotation.quotation_code:
                raise InvalidRecordStateError(
                    f"La factura {invoice.invoice_id} no pertenece a "
                    f"la cotización {quotation.quotation_code}."
                )

            if invoice.verification_status in {
                VerificationStatus.POSSIBLE_DUPLICATE,
                VerificationStatus.ERROR,
            }:
                raise InvalidRecordStateError(
                    f"La factura {invoice.invoice_id} tiene estado "
                    f"{invoice.verification_status.value} y no puede "
                    "recibir pagos."
                )

        prepared = self._images.prepare(image_paths)
        extraction = (
            confirmed_extraction
            if confirmed_extraction is not None
            else self._provider.extract(
                prepared,
                DocumentType.PAYMENT_RECEIPT,
            )
        )
        validation = self._validator.validate_payment(extraction)

        duplicates = self._duplicates.find_matches(
            extraction,
            prepared.source_hash,
            self._repository.list_document_references(),
        )

        payment_reconciliation = None

        if invoice is not None:
            previously_paid = (
                self._repository.get_verified_payment_total(
                    invoice.invoice_id
                )
            )

            payment_reconciliation = (
                self._payment_reconciliation.compare(
                    invoice,
                    extraction,
                    previously_paid,
                    apply_payment=not duplicates,
                )
            )

            status = resolve_verification_status(
                validation,
                duplicates,
                payment_reconciliation,
            )

            if (
                status != VerificationStatus.VERIFIED
                and payment_reconciliation.applied
            ):
                payment_reconciliation = (
                    self._payment_reconciliation.reject_application(
                        payment_reconciliation,
                        invoice.payment_status,
                    )
                )

            reconciliation_status = (
                PaymentLinkStatus.RECONCILED
                if payment_reconciliation.applied
                else PaymentLinkStatus.REVIEW
            )
        else:
            status = resolve_verification_status(
                validation,
                duplicates,
            )

            reconciliation_status = (
                PaymentLinkStatus.PENDING_INVOICE
                if status == VerificationStatus.VERIFIED
                else PaymentLinkStatus.REVIEW
            )

        observations = [
            *extraction.observations,
            *issue_messages(
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

        record = PaymentRecord(
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
            source_files=prepared.source_names,
            duplicate_of=[
                match.document_id
                for match in duplicates
            ],
            observations=self._unique(observations),
        )

        self._repository.add_payment(
            record,
            invoice,
            payment_reconciliation,
        )

        return RegistrationResult(
            document_id=payment_id,
            document_type=extraction.document_type,
            verification_status=status,
            workbook_path=self._repository.location,
            validation=validation,
            duplicates=duplicates,
            payment_reconciliation=payment_reconciliation,
        )

    def link_payment(
        self,
        payment_id: str,
        invoice_id: str,
    ) -> PaymentLinkResult:
        self._repository.initialize()

        payment = self._repository.get_payment(payment_id)
        if payment is None:
            raise RecordNotFoundError(
                f"No existe el pago "
                f"{payment_id.strip().upper()}."
            )

        invoice = self._repository.get_invoice(invoice_id)
        if invoice is None:
            raise RecordNotFoundError(
                f"No existe la factura "
                f"{invoice_id.strip().upper()}."
            )

        if (
            payment.verification_status
            != VerificationStatus.VERIFIED
        ):
            raise InvalidRecordStateError(
                f"El pago {payment.payment_id} tiene estado "
                f"{payment.verification_status.value} "
                "y no puede conciliarse."
            )

        if (
            payment.reconciliation_status
            != PaymentLinkStatus.PENDING_INVOICE
        ):
            raise InvalidRecordStateError(
                f"El pago {payment.payment_id} tiene estado "
                f"de conciliación "
                f"{payment.reconciliation_status.value}."
            )

        if invoice.verification_status in {
            VerificationStatus.POSSIBLE_DUPLICATE,
            VerificationStatus.ERROR,
        }:
            raise InvalidRecordStateError(
                f"La factura {invoice.invoice_id} tiene estado "
                f"{invoice.verification_status.value} "
                "y no puede recibir pagos."
            )

        if payment.quotation_code != invoice.quotation_code:
            raise InvalidRecordStateError(
                f"El pago {payment.payment_id} y la factura "
                f"{invoice.invoice_id} pertenecen a "
                "cotizaciones diferentes."
            )

        extraction = DocumentExtraction(
            document_type=payment.payment_type,
            document_date=payment.payment_date,
            total_amount=payment.paid_amount,
            currency=payment.currency,
            operation_number=payment.operation_number,
            payment_entity=payment.payment_entity,
            confidence=1,
        )

        previously_paid = (
            self._repository.get_verified_payment_total(
                invoice.invoice_id
            )
        )

        reconciliation = self._payment_reconciliation.compare(
            invoice,
            extraction,
            previously_paid,
        )

        applied = not reconciliation.issues

        if not applied:
            reconciliation = (
                self._payment_reconciliation.reject_application(
                    reconciliation,
                    invoice.payment_status,
                )
            )

        reconciliation_status = (
            PaymentLinkStatus.RECONCILED
            if applied
            else PaymentLinkStatus.REVIEW
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

        self._repository.link_payment(
            updated_payment,
            invoice,
            reconciliation,
        )

        return PaymentLinkResult(
            payment_id=payment.payment_id,
            invoice_id=invoice.invoice_id,
            quotation_code=payment.quotation_code,
            reconciliation_status=reconciliation_status,
            workbook_path=self._repository.location,
            payment_reconciliation=reconciliation,
        )

    @staticmethod
    def _unique(values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip() for value in values if value and value.strip()))

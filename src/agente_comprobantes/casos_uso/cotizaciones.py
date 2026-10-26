from __future__ import annotations

from agente_comprobantes.dominio import (
    ExtraccionDocumento,
    TipoDocumento,
    RegistroCotizacion,
    EstadoCotizacion,
    ResultadoRegistro,
)
from agente_comprobantes.servicios.estados import issue_messages, resolve_verification_status


class OperacionesCotizaciones:
    def register_quotation(
        self,
        quotation_code: str,
        image_paths: list[str],
        *,
        confirmed_extraction: ExtraccionDocumento | None = None,
    ) -> ResultadoRegistro:
        self._repository.initialize()
        prepared = self._images.prepare(image_paths)
        extraction = (
            confirmed_extraction
            if confirmed_extraction is not None
            else self._provider.extract(
                prepared,
                TipoDocumento.QUOTATION,
            )
        )
        validation = self._validator.validate(extraction, TipoDocumento.QUOTATION)
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

        record = RegistroCotizacion(
            quotation_code=quotation_code,
            provider=extraction.provider,
            provider_tax_id=extraction.provider_tax_id,
            concept=extraction.concept,
            quoted_amount=extraction.total_amount,
            currency=extraction.currency,
            quotation_date=extraction.document_date,
            status=EstadoCotizacion.WAITING_INVOICE,
            verification_status=status,
            source_hash=prepared.source_hash,
            source_files=prepared.source_names,
            uncertain_fields=extraction.uncertain_fields,
            observations=self._unique(observations),
        )
        self._repository.add_quotation(record)
        return ResultadoRegistro(
            document_id=record.quotation_code,
            document_type=TipoDocumento.QUOTATION,
            verification_status=status,
            workbook_path=self._repository.location,
            validation=validation,
            duplicates=duplicates,
        )

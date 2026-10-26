from __future__ import annotations

from agente_comprobantes.dominio import (
    EstadoCotizacion,
    ExtraccionDocumento,
    RegistroCotizacion,
    ResultadoRegistro,
    TipoDocumento,
)
from agente_comprobantes.servicios.estados import mensajes_observaciones, resolver_estado_verificacion


class OperacionesCotizaciones:
    def registrar_cotizacion(
        self,
        quotation_code: str,
        image_paths: list[str],
        *,
        confirmed_extraction: ExtraccionDocumento | None = None,
    ) -> ResultadoRegistro:
        self._repository.inicializar()
        prepared = self._images.preparar(image_paths)
        extraction = (
            confirmed_extraction
            if confirmed_extraction is not None
            else self._provider.extraer(
                prepared,
                TipoDocumento.QUOTATION,
            )
        )
        validation = self._validator.validar(extraction, TipoDocumento.QUOTATION)
        duplicates = self._duplicates.buscar_coincidencias(
            extraction, prepared.source_hash, self._repository.listar_referencias_documentos()
        )
        status = resolver_estado_verificacion(validation, duplicates)
        observations = [*extraction.observations, *mensajes_observaciones(validation)]
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
            source_files=prepared.nombres_archivos,
            uncertain_fields=extraction.uncertain_fields,
            observations=self._unique(observations),
        )
        self._repository.agregar_cotizacion(record)
        return ResultadoRegistro(
            document_id=record.quotation_code,
            document_type=TipoDocumento.QUOTATION,
            verification_status=status,
            workbook_path=self._repository.ubicacion,
            validation=validation,
            duplicates=duplicates,
        )

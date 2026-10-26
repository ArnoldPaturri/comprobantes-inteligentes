from __future__ import annotations

from uuid import uuid4

from agente_comprobantes.dominio import (
    EstadoPago,
    ExtraccionDocumento,
    RegistroFactura,
    ResultadoRegistro,
    TipoDocumento,
)
from agente_comprobantes.excepciones import ErrorRegistroNoEncontrado
from agente_comprobantes.servicios.estados import (
    mensajes_observaciones,
    resolver_estado_verificacion,
)


class OperacionesFacturas:
    def registrar_factura(
        self,
        quotation_code: str,
        image_paths: list[str],
        *,
        confirmed_extraction: ExtraccionDocumento | None = None,
    ) -> ResultadoRegistro:
        self._repository.inicializar()
        quotation = self._repository.obtener_cotizacion(quotation_code)
        if quotation is None:
            raise ErrorRegistroNoEncontrado(
                f"No existe la cotización {quotation_code.strip().upper()}. "
                "Regístrala antes de procesar la factura."
            )

        prepared = self._images.preparar(image_paths)
        extraction = (
            confirmed_extraction
            if confirmed_extraction is not None
            else self._provider.extraer(
                prepared,
                TipoDocumento.INVOICE,
            )
        )
        validation = self._validator.validar(extraction, TipoDocumento.INVOICE)
        duplicates = self._duplicates.buscar_coincidencias(
            extraction, prepared.source_hash, self._repository.listar_referencias_documentos()
        )
        reconciliation = self._reconciliation.comparar(quotation, extraction)
        status = resolver_estado_verificacion(validation, duplicates, reconciliation)
        observations = [
            *extraction.observations,
            *mensajes_observaciones(validation, reconciliation),
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
            source_files=prepared.nombres_archivos,
            uncertain_fields=extraction.uncertain_fields,
            duplicate_of=[match.document_id for match in duplicates],
            observations=self._unique(observations),
        )
        self._repository.agregar_factura(record, quotation, reconciliation)
        return ResultadoRegistro(
            document_id=invoice_id,
            document_type=TipoDocumento.INVOICE,
            verification_status=status,
            workbook_path=self._repository.ubicacion,
            validation=validation,
            duplicates=duplicates,
            reconciliation=reconciliation,
        )

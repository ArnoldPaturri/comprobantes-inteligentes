from agente_comprobantes.configuracion import Configuracion
from agente_comprobantes.dominio import (
    ExtraccionDocumento,
    InformeValidacion,
    ObservacionValidacion,
    Severidad,
    TipoDocumento,
)

REQUIRED_FIELDS: dict[TipoDocumento, tuple[str, ...]] = {
    TipoDocumento.QUOTATION: ("provider", "concept", "total_amount"),
    TipoDocumento.INVOICE: ("provider", "document_number", "document_date", "total_amount"),
    TipoDocumento.RECEIPT: ("provider", "document_number", "document_date", "total_amount"),
    TipoDocumento.BANK_TRANSFER: ("total_amount", "document_date", "operation_number"),
    TipoDocumento.YAPE: ("total_amount", "document_date", "operation_number"),
    TipoDocumento.PLIN: ("total_amount", "document_date", "operation_number"),
    TipoDocumento.POS_VOUCHER: ("total_amount", "document_date", "operation_number"),
    TipoDocumento.DEPOSIT: ("total_amount", "document_date", "operation_number"),
    TipoDocumento.PAYMENT_RECEIPT: ("total_amount", "document_date"),
}

PAYMENT_DOCUMENT_TYPES = frozenset(
    {
        TipoDocumento.BANK_TRANSFER,
        TipoDocumento.YAPE,
        TipoDocumento.PLIN,
        TipoDocumento.POS_VOUCHER,
        TipoDocumento.DEPOSIT,
        TipoDocumento.PAYMENT_RECEIPT,
    }
)


class ServicioValidacion:
    def __init__(self, settings: Configuracion) -> None:
        self._settings = settings

    def validate(
        self,
        extraction: ExtraccionDocumento,
        expected_type: TipoDocumento,
    ) -> InformeValidacion:
        return self._validate(extraction, expected_type, {expected_type})

    def validate_payment(self, extraction: ExtraccionDocumento) -> InformeValidacion:
        """Acepta las variantes soportadas de un comprobante de pago."""

        return self._validate(
            extraction,
            TipoDocumento.PAYMENT_RECEIPT,
            PAYMENT_DOCUMENT_TYPES,
        )

    def _validate(
        self,
        extraction: ExtraccionDocumento,
        expected_type: TipoDocumento,
        accepted_types: set[TipoDocumento] | frozenset[TipoDocumento],
    ) -> InformeValidacion:
        issues: list[ObservacionValidacion] = []

        if extraction.document_type not in accepted_types:
            expected_label = (
                "un comprobante de pago válido"
                if len(accepted_types) > 1
                else expected_type.value
            )
            issues.append(
                ObservacionValidacion(
                    code="DOCUMENT_TYPE_MISMATCH",
                    severity=Severidad.ERROR,
                    field="document_type",
                    message=(
                        f"Se esperaba {expected_label}, pero la imagen parece "
                        f"{extraction.document_type.value}."
                    ),
                )
            )

        required_type = (
            extraction.document_type
            if extraction.document_type in accepted_types
            else expected_type
        )
        for field_name in REQUIRED_FIELDS.get(required_type, ()):
            if getattr(extraction, field_name) in (None, ""):
                issues.append(
                    ObservacionValidacion(
                        code="MISSING_CRITICAL_FIELD",
                        severity=Severidad.ERROR,
                        field=field_name,
                        message=f"No se pudo extraer el campo obligatorio: {field_name}.",
                    )
                )

        if extraction.total_amount is not None and extraction.total_amount < 0:
            issues.append(
                ObservacionValidacion(
                    code="NEGATIVE_AMOUNT",
                    severity=Severidad.ERROR,
                    field="total_amount",
                    message="El monto total no puede ser negativo.",
                )
            )

        if extraction.provider_tax_id and len(extraction.provider_tax_id) != 11:
            issues.append(
                ObservacionValidacion(
                    code="INVALID_PERUVIAN_RUC",
                    severity=Severidad.WARNING,
                    field="provider_tax_id",
                    message="El RUC detectado no contiene 11 dígitos.",
                )
            )

        if not 0 <= extraction.confidence <= 1:
            issues.append(
                ObservacionValidacion(
                    code="INVALID_CONFIDENCE",
                    severity=Severidad.ERROR,
                    field="confidence",
                    message="La confianza debe estar entre 0 y 1.",
                )
            )
        elif extraction.confidence < self._settings.min_extraction_confidence:
            issues.append(
                ObservacionValidacion(
                    code="LOW_CONFIDENCE",
                    severity=Severidad.WARNING,
                    field="confidence",
                    message=f"Confianza de extracción baja ({extraction.confidence:.0%}).",
                )
            )

        for field_name in extraction.uncertain_fields:
            issues.append(
                ObservacionValidacion(
                    code="UNCERTAIN_FIELD",
                    severity=Severidad.WARNING,
                    field=field_name,
                    message=f"El campo {field_name} requiere revisión visual.",
                )
            )

        return InformeValidacion(issues=self._deduplicate(issues))

    @staticmethod
    def _deduplicate(issues: list[ObservacionValidacion]) -> list[ObservacionValidacion]:
        seen: set[tuple[str, str | None]] = set()
        result: list[ObservacionValidacion] = []
        for issue in issues:
            key = (issue.code, issue.field)
            if key not in seen:
                seen.add(key)
                result.append(issue)
        return result

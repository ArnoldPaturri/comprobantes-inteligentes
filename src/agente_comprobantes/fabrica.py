from agente_comprobantes.agente import ReceiptAgent
from agente_comprobantes.configuracion import Settings
from agente_comprobantes.proveedores import (
    CohereVisionProvider,
    FallbackVisionProvider,
    GroqVisionProvider,
    VisionProvider,
)
from agente_comprobantes.repositorios import DocumentRepository, ExcelRepository
from agente_comprobantes.servicios.duplicados import DuplicateService
from agente_comprobantes.servicios.imagenes import ImageService
from agente_comprobantes.servicios.conciliacion_pagos import PaymentReconciliationService
from agente_comprobantes.servicios.conciliacion_facturas import ReconciliationService
from agente_comprobantes.servicios.validacion import ValidationService


def build_repository(settings: Settings) -> ExcelRepository:
    return ExcelRepository(settings.resolved_workbook_path())

def build_vision_provider(
    settings: Settings,
) -> VisionProvider:
    selected = settings.vision_provider

    if selected == "groq":
        return GroqVisionProvider(settings)

    if selected == "cohere":
        return CohereVisionProvider(settings)

    providers: list[tuple[str, VisionProvider]] = []

    if settings.has_groq_api_key():
        providers.append(
            ("Groq", GroqVisionProvider(settings))
        )

    if settings.has_cohere_api_key():
        providers.append(
            ("Cohere", CohereVisionProvider(settings))
        )

    if not providers:
        raise ValueError(
            "No existe ningún proveedor de visión configurado. "
            "Agrega GROQ_API_KEY o COHERE_API_KEY en .env."
        )

    if len(providers) == 1:
        return providers[0][1]

    return FallbackVisionProvider(providers)

def build_agent(
    settings: Settings,
    provider: VisionProvider | None = None,
    repository: DocumentRepository | None = None,
) -> ReceiptAgent:
    return ReceiptAgent(
        provider=provider or build_vision_provider(settings),
        repository=repository or build_repository(settings),
        image_service=ImageService(settings),
        validation_service=ValidationService(settings),
        duplicate_service=DuplicateService(),
        reconciliation_service=ReconciliationService(settings),
        payment_reconciliation_service=PaymentReconciliationService(),
    )

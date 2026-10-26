from invoice_agent.agent import ReceiptAgent
from invoice_agent.config import Settings
from invoice_agent.providers import (
    CohereVisionProvider,
    FallbackVisionProvider,
    GroqVisionProvider,
    VisionProvider,
)
from invoice_agent.repositories import DocumentRepository, ExcelRepository
from invoice_agent.services.duplicate_service import DuplicateService
from invoice_agent.services.image_service import ImageService
from invoice_agent.services.payment_reconciliation_service import PaymentReconciliationService
from invoice_agent.services.reconciliation_service import ReconciliationService
from invoice_agent.services.validation_service import ValidationService


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

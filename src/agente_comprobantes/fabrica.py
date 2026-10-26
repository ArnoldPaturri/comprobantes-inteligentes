from agente_comprobantes.agente import AgenteComprobantes
from agente_comprobantes.configuracion import Configuracion
from agente_comprobantes.proveedores import (
    ProveedorVision,
    ProveedorVisionCohere,
    ProveedorVisionGroq,
    ProveedorVisionRespaldo,
)
from agente_comprobantes.repositorios import RepositorioDocumentos, RepositorioExcel
from agente_comprobantes.servicios.conciliacion_facturas import ServicioConciliacionFacturas
from agente_comprobantes.servicios.conciliacion_pagos import ServicioConciliacionPagos
from agente_comprobantes.servicios.duplicados import ServicioDuplicados
from agente_comprobantes.servicios.imagenes import ServicioImagenes
from agente_comprobantes.servicios.validacion import ServicioValidacion


def build_repository(settings: Configuracion) -> RepositorioExcel:
    return RepositorioExcel(settings.resolved_workbook_path())

def build_vision_provider(
    settings: Configuracion,
) -> ProveedorVision:
    selected = settings.vision_provider

    if selected == "groq":
        return ProveedorVisionGroq(settings)

    if selected == "cohere":
        return ProveedorVisionCohere(settings)

    providers: list[tuple[str, ProveedorVision]] = []

    if settings.has_groq_api_key():
        providers.append(
            ("Groq", ProveedorVisionGroq(settings))
        )

    if settings.has_cohere_api_key():
        providers.append(
            ("Cohere", ProveedorVisionCohere(settings))
        )

    if not providers:
        raise ValueError(
            "No existe ningún proveedor de visión configurado. "
            "Agrega GROQ_API_KEY o COHERE_API_KEY en .env."
        )

    if len(providers) == 1:
        return providers[0][1]

    return ProveedorVisionRespaldo(providers)

def build_agent(
    settings: Configuracion,
    provider: ProveedorVision | None = None,
    repository: RepositorioDocumentos | None = None,
) -> AgenteComprobantes:
    return AgenteComprobantes(
        provider=provider or build_vision_provider(settings),
        repository=repository or build_repository(settings),
        image_service=ServicioImagenes(settings),
        validation_service=ServicioValidacion(settings),
        duplicate_service=ServicioDuplicados(),
        reconciliation_service=ServicioConciliacionFacturas(settings),
        payment_reconciliation_service=ServicioConciliacionPagos(),
    )

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


def crear_repositorio(settings: Configuracion) -> RepositorioExcel:
    return RepositorioExcel(settings.ruta_archivo_excel())

def crear_proveedor_vision(
    settings: Configuracion,
) -> ProveedorVision:
    selected = settings.vision_provider

    if selected == "groq":
        return ProveedorVisionGroq(settings)

    if selected == "cohere":
        return ProveedorVisionCohere(settings)

    providers: list[tuple[str, ProveedorVision]] = []

    if settings.tiene_clave_groq():
        providers.append(
            ("Groq", ProveedorVisionGroq(settings))
        )

    if settings.tiene_clave_cohere():
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

def crear_agente(
    settings: Configuracion,
    provider: ProveedorVision | None = None,
    repository: RepositorioDocumentos | None = None,
) -> AgenteComprobantes:
    return AgenteComprobantes(
        provider=provider or crear_proveedor_vision(settings),
        repository=repository or crear_repositorio(settings),
        image_service=ServicioImagenes(settings),
        validation_service=ServicioValidacion(settings),
        duplicate_service=ServicioDuplicados(),
        reconciliation_service=ServicioConciliacionFacturas(settings),
        payment_reconciliation_service=ServicioConciliacionPagos(),
    )

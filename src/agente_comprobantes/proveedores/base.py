from abc import ABC, abstractmethod

from agente_comprobantes.dominio import ExtraccionDocumento, TipoDocumento
from agente_comprobantes.servicios.imagenes import DocumentoPreparado


class ProveedorVision(ABC):
    """Puerto de salida para proveedores multimodales."""

    @abstractmethod
    def extract(
        self,
        document: DocumentoPreparado,
        expected_type: TipoDocumento,
    ) -> ExtraccionDocumento:
        raise NotImplementedError


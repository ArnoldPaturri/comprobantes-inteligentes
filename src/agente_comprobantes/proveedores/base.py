from abc import ABC, abstractmethod

from agente_comprobantes.dominio import DocumentExtraction, DocumentType
from agente_comprobantes.servicios.imagenes import PreparedDocument


class VisionProvider(ABC):
    """Puerto de salida para proveedores multimodales."""

    @abstractmethod
    def extract(
        self,
        document: PreparedDocument,
        expected_type: DocumentType,
    ) -> DocumentExtraction:
        raise NotImplementedError


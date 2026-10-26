from abc import ABC, abstractmethod

from invoice_agent.domain import DocumentExtraction, DocumentType
from invoice_agent.services.image_service import PreparedDocument


class VisionProvider(ABC):
    """Puerto de salida para proveedores multimodales."""

    @abstractmethod
    def extract(
        self,
        document: PreparedDocument,
        expected_type: DocumentType,
    ) -> DocumentExtraction:
        raise NotImplementedError


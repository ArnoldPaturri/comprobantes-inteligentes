from collections import deque

from agente_comprobantes.dominio import DocumentExtraction, DocumentType
from agente_comprobantes.proveedores.base import VisionProvider
from agente_comprobantes.servicios.imagenes import PreparedDocument


class FakeVisionProvider(VisionProvider):
    def __init__(self, *responses: DocumentExtraction) -> None:
        self.responses = deque(responses)
        self.calls: list[tuple[PreparedDocument, DocumentType]] = []

    def extract(
        self,
        document: PreparedDocument,
        expected_type: DocumentType,
    ) -> DocumentExtraction:
        self.calls.append((document, expected_type))
        return self.responses.popleft()


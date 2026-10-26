from collections import deque

from invoice_agent.domain import DocumentExtraction, DocumentType
from invoice_agent.providers.base import VisionProvider
from invoice_agent.services.image_service import PreparedDocument


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


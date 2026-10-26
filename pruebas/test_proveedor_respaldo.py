from agente_comprobantes.dominio import DocumentExtraction, DocumentType
from agente_comprobantes.excepciones import ExtractionError
from agente_comprobantes.proveedores.base import VisionProvider
from agente_comprobantes.proveedores.respaldo import FallbackVisionProvider
from agente_comprobantes.servicios.imagenes import PreparedDocument


class StubProvider(VisionProvider):
    def __init__(
        self,
        result: DocumentExtraction | None = None,
        error: str | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.calls = 0

    def extract(
        self,
        document: PreparedDocument,
        expected_type: DocumentType,
    ) -> DocumentExtraction:
        self.calls += 1

        if self.error is not None:
            raise ExtractionError(self.error)

        assert self.result is not None
        return self.result


def _document() -> PreparedDocument:
    return PreparedDocument(
        images=(),
        source_hash="a" * 64,
    )


def test_uses_second_provider_when_first_fails() -> None:
    first = StubProvider(error="timeout")
    expected = DocumentExtraction(
        document_type=DocumentType.QUOTATION,
        confidence=0.95,
    )
    second = StubProvider(result=expected)

    provider = FallbackVisionProvider(
        [
            ("primero", first),
            ("segundo", second),
        ]
    )

    result = provider.extract(
        _document(),
        DocumentType.QUOTATION,
    )

    assert result == expected
    assert first.calls == 1
    assert second.calls == 1


def test_does_not_call_fallback_after_success() -> None:
    expected = DocumentExtraction(
        document_type=DocumentType.QUOTATION,
        confidence=0.95,
    )
    first = StubProvider(result=expected)
    second = StubProvider(error="no debería ejecutarse")

    provider = FallbackVisionProvider(
        [
            ("primero", first),
            ("segundo", second),
        ]
    )

    result = provider.extract(
        _document(),
        DocumentType.QUOTATION,
    )

    assert result == expected
    assert first.calls == 1
    assert second.calls == 0
from agente_comprobantes.dominio import ExtraccionDocumento, TipoDocumento
from agente_comprobantes.excepciones import ErrorExtraccion
from agente_comprobantes.proveedores.base import ProveedorVision
from agente_comprobantes.proveedores.respaldo import ProveedorVisionRespaldo
from agente_comprobantes.servicios.imagenes import DocumentoPreparado


class StubProvider(ProveedorVision):
    def __init__(
        self,
        result: ExtraccionDocumento | None = None,
        error: str | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.calls = 0

    def extraer(
        self,
        document: DocumentoPreparado,
        expected_type: TipoDocumento,
    ) -> ExtraccionDocumento:
        self.calls += 1

        if self.error is not None:
            raise ErrorExtraccion(self.error)

        assert self.result is not None
        return self.result


def _document() -> DocumentoPreparado:
    return DocumentoPreparado(
        images=(),
        source_hash="a" * 64,
    )


def test_uses_second_provider_when_first_fails() -> None:
    first = StubProvider(error="timeout")
    expected = ExtraccionDocumento(
        document_type=TipoDocumento.QUOTATION,
        confidence=0.95,
    )
    second = StubProvider(result=expected)

    provider = ProveedorVisionRespaldo(
        [
            ("primero", first),
            ("segundo", second),
        ]
    )

    result = provider.extraer(
        _document(),
        TipoDocumento.QUOTATION,
    )

    assert result == expected
    assert first.calls == 1
    assert second.calls == 1


def test_does_not_call_fallback_after_success() -> None:
    expected = ExtraccionDocumento(
        document_type=TipoDocumento.QUOTATION,
        confidence=0.95,
    )
    first = StubProvider(result=expected)
    second = StubProvider(error="no debería ejecutarse")

    provider = ProveedorVisionRespaldo(
        [
            ("primero", first),
            ("segundo", second),
        ]
    )

    result = provider.extraer(
        _document(),
        TipoDocumento.QUOTATION,
    )

    assert result == expected
    assert first.calls == 1
    assert second.calls == 0
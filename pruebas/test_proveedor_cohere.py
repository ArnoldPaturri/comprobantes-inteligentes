import json
from types import SimpleNamespace

from agente_comprobantes.dominio import DocumentType
from agente_comprobantes.proveedores.vision_cohere import CohereVisionProvider
from agente_comprobantes.servicios.imagenes import ImageService


class FakeCohereClient:
    def __init__(self) -> None:
        self.kwargs = None

    def chat(self, **kwargs):
        self.kwargs = kwargs
        payload = {
            "document_type": "FACTURA",
            "provider": "Proveedor SAC",
            "provider_tax_id": "20123456789",
            "concept": "Servicio",
            "document_number": "F001-1",
            "document_date": "2026-09-12",
            "total_amount": 100.5,
            "currency": "PEN",
            "operation_number": None,
            "payment_entity": None,
            "quotation_reference": None,
            "confidence": 0.95,
            "uncertain_fields": [],
            "observations": [],
        }
        block = SimpleNamespace(text=json.dumps(payload))
        return SimpleNamespace(message=SimpleNamespace(content=[block]))


def test_provider_sends_schema_and_all_images(settings, make_image) -> None:
    client = FakeCohereClient()
    provider = CohereVisionProvider(settings, client=client)
    prepared = ImageService(settings).prepare(
        [make_image("one.png"), make_image("two.png", color="gray")]
    )

    result = provider.extract(prepared, DocumentType.INVOICE)

    assert result.document_number == "F001-1"
    assert client.kwargs["model"] == "command-a-vision-07-2025"
    assert client.kwargs["response_format"]["type"] == "json_object"
    assert len(client.kwargs["messages"][0]["content"]) == 3


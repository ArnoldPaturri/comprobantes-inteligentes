from collections import deque

from agente_comprobantes.dominio import ExtraccionDocumento, TipoDocumento
from agente_comprobantes.proveedores.base import ProveedorVision
from agente_comprobantes.servicios.imagenes import DocumentoPreparado


class ProveedorVisionSimulado(ProveedorVision):
    def __init__(self, *responses: ExtraccionDocumento) -> None:
        self.responses = deque(responses)
        self.calls: list[tuple[DocumentoPreparado, TipoDocumento]] = []

    def extract(
        self,
        document: DocumentoPreparado,
        expected_type: TipoDocumento,
    ) -> ExtraccionDocumento:
        self.calls.append((document, expected_type))
        return self.responses.popleft()


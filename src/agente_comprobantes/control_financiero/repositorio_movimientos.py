"""Repositorio atómico INDEPENDIENTE para movimientos bancarios centrales."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from agente_comprobantes.control_financiero.movimientos_centrales import (
    MovimientoBancarioCentral,
)
from agente_comprobantes.control_financiero.auditoria_importacion import (
    normalizar_referencia_para_busqueda,
)


def clave_movimiento(movimiento: MovimientoBancarioCentral) -> tuple[str, str, str]:
    return (
        movimiento.banco.casefold().strip(),
        normalizar_referencia_para_busqueda(movimiento.referencia),
        movimiento.moneda.value,
    )


class RepositorioMovimientosCentrales:
    VERSION = 1

    def __init__(self, ruta: str | Path) -> None:
        self.ruta = Path(ruta).expanduser().resolve()

    def listar(self) -> list[MovimientoBancarioCentral]:
        if not self.ruta.exists():
            return []
        datos = json.loads(self.ruta.read_text(encoding="utf-8"))
        if (
            not isinstance(datos, dict)
            or datos.get("version") != self.VERSION
            or not isinstance(datos.get("movimientos"), list)
        ):
            raise ValueError("El registro bancario tiene un formato inválido.")
        movimientos = [
            MovimientoBancarioCentral.model_validate(item)
            for item in datos["movimientos"]
        ]
        self._validar_unicidad(movimientos)
        return movimientos

    def huella(self) -> str:
        if not self.ruta.exists():
            return "sin-archivo"
        return hashlib.sha256(self.ruta.read_bytes()).hexdigest()

    @staticmethod
    def _validar_unicidad(movimientos: list[MovimientoBancarioCentral]) -> None:
        ids = [m.identificador for m in movimientos]
        claves = [clave_movimiento(m) for m in movimientos]
        if len(ids) != len(set(ids)) or len(claves) != len(set(claves)):
            raise ValueError("Hay movimientos centrales duplicados.")

    def agregar(
        self,
        movimiento: MovimientoBancarioCentral,
        *,
        huella_esperada: str,
    ) -> None:
        if self.huella() != huella_esperada:
            raise ValueError("El registro bancario cambió; vuelve a revisar.")
        actuales = self.listar()
        nuevos = [*actuales, movimiento]
        self._validar_unicidad(nuevos)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": self.VERSION,
            "movimientos": [m.model_dump(mode="json") for m in nuevos],
        }
        temporal: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8",
                prefix=".movimientos_", suffix=".tmp",
                dir=self.ruta.parent, delete=False,
            ) as archivo:
                temporal = archivo.name
                json.dump(payload, archivo, ensure_ascii=False, indent=2)
                archivo.flush()
                os.fsync(archivo.fileno())
            if self.huella() != huella_esperada:
                raise ValueError("El registro bancario cambió durante el guardado.")
            os.replace(temporal, self.ruta)
        finally:
            if temporal is not None and os.path.exists(temporal):
                os.unlink(temporal)

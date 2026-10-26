"""Persistencia aislada para control financiero de fletes.

Este repositorio no escribe ni modifica el Excel operativo original.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from agente_comprobantes.control_financiero.modelos import OperacionFlete


class RepositorioControlFletes:
    VERSION = 1

    def __init__(self, ruta: str | Path) -> None:
        self._ruta = Path(ruta).expanduser().resolve()

    @property
    def ubicacion(self) -> str:
        return str(self._ruta)

    def listar(self) -> list[OperacionFlete]:
        if not self._ruta.exists():
            return []
        with self._ruta.open("r", encoding="utf-8") as archivo:
            datos = json.load(archivo)
        if (
            not isinstance(datos, dict)
            or datos.get("version") != self.VERSION
            or not isinstance(datos.get("operaciones"), list)
        ):
            raise ValueError("El archivo de control financiero tiene un formato inválido.")
        operaciones = [
            OperacionFlete.model_validate(item) for item in datos["operaciones"]
        ]
        self._validar_unicidad(operaciones)
        return operaciones

    def obtener(self, identificador: str) -> OperacionFlete | None:
        codigo = identificador.strip().upper()
        return next(
            (
                operacion for operacion in self.listar()
                if operacion.identificador.strip().upper() == codigo
            ),
            None,
        )

    def agregar(self, operacion: OperacionFlete) -> None:
        operaciones = self.listar()
        operaciones.append(operacion)
        self._validar_unicidad(operaciones)
        self._guardar_atomico(operaciones)

    def actualizar(self, operacion: OperacionFlete) -> None:
        operaciones = self.listar()
        codigo = operacion.identificador.strip().upper()
        for indice, anterior in enumerate(operaciones):
            if anterior.identificador.strip().upper() == codigo:
                operaciones[indice] = operacion
                self._validar_unicidad(operaciones)
                self._guardar_atomico(operaciones)
                return
        raise ValueError(f"El control de flete {operacion.identificador} no existe.")

    @staticmethod
    def _validar_unicidad(operaciones: list[OperacionFlete]) -> None:
        identificadores: set[str] = set()
        for operacion in operaciones:
            codigo = operacion.identificador.strip().upper()
            if codigo in identificadores:
                raise ValueError(f"Ya existe el control de flete {codigo}.")
            identificadores.add(codigo)

    def _guardar_atomico(self, operaciones: list[OperacionFlete]) -> None:
        self._ruta.parent.mkdir(parents=True, exist_ok=True)
        contenido = {
            "version": self.VERSION,
            "operaciones": [
                operacion.model_dump(mode="json") for operacion in operaciones
            ],
        }
        temporal: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                prefix=".fletes_",
                suffix=".tmp",
                dir=self._ruta.parent,
                delete=False,
            ) as archivo:
                temporal = archivo.name
                json.dump(contenido, archivo, ensure_ascii=False, indent=2)
                archivo.flush()
                os.fsync(archivo.fileno())
            os.replace(temporal, self._ruta)
        finally:
            if temporal is not None and os.path.exists(temporal):
                os.unlink(temporal)

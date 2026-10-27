"""Persistencia aislada para control financiero de fletes.

Este repositorio no escribe ni modifica el Excel operativo original.
"""

from __future__ import annotations

import hashlib
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

    def huella(self) -> str:
        """Versión del archivo para evitar guardar una vista previa obsoleta."""
        if not self._ruta.exists():
            return "sin-archivo"
        return hashlib.sha256(self._ruta.read_bytes()).hexdigest()

    def agregar_lote(
        self,
        nuevas: list[OperacionFlete],
        *,
        huella_esperada: str,
    ) -> None:
        """Incorpora el lote validado en una sola escritura atómica.

        Protege ID y factura/proveedor; no sobrescribe operaciones revisadas.
        Se destina a un único operador local, no a edición concurrente.
        """
        if not nuevas:
            raise ValueError("El lote de importación no tiene operaciones.")
        if self.huella() != huella_esperada:
            raise ValueError("El archivo de control cambió; genera otra vista previa.")
        actuales = self.listar()
        existentes = {
            (op.numero_factura.strip().casefold(), (op.proveedor or "").strip().casefold())
            for op in actuales
        }
        nuevos_pares: set[tuple[str, str]] = set()
        for op in nuevas:
            par = (
                op.numero_factura.strip().casefold(),
                (op.proveedor or "").strip().casefold(),
            )
            if par in existentes or par in nuevos_pares:
                raise ValueError("La importación contiene facturas repetidas.")
            nuevos_pares.add(par)
        conjunto = [*actuales, *nuevas]
        self._validar_unicidad(conjunto)
        self._guardar_atomico(conjunto)

    def actualizar_lote(
        self,
        operaciones: list[OperacionFlete],
        *,
        huella_esperada: str,
    ) -> None:
        """Actualiza varios expedientes en una única escritura atómica y versionada."""
        if not operaciones:
            raise ValueError("No hay expedientes que actualizar.")
        if self.huella() != huella_esperada:
            raise ValueError("El archivo de control cambió; vuelve a revisar.")
        codigos = [op.identificador.strip().upper() for op in operaciones]
        if len(codigos) != len(set(codigos)):
            raise ValueError("El lote contiene expedientes repetidos.")
        actuales = self.listar()
        posiciones = {
            op.identificador.strip().upper(): indice
            for indice, op in enumerate(actuales)
        }
        faltantes = [codigo for codigo in codigos if codigo not in posiciones]
        if faltantes:
            raise ValueError(
                "No existen los expedientes: " + ", ".join(faltantes)
            )
        for codigo, nueva in zip(codigos, operaciones, strict=True):
            actuales[posiciones[codigo]] = nueva
        self._validar_unicidad(actuales)
        self._guardar_atomico(actuales, huella_esperada=huella_esperada)

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

    def _guardar_atomico(
        self,
        operaciones: list[OperacionFlete],
        *,
        huella_esperada: str | None = None,
    ) -> None:
        if huella_esperada is not None and self.huella() != huella_esperada:
            raise ValueError("El archivo de control cambió antes de escribir.")
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
            if huella_esperada is not None and self.huella() != huella_esperada:
                raise ValueError("El archivo de control cambió durante el guardado.")
            os.replace(temporal, self._ruta)
        finally:
            if temporal is not None and os.path.exists(temporal):
                os.unlink(temporal)

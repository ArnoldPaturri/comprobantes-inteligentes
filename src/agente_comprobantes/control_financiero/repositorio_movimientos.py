"""Repositorio atómico INDEPENDIENTE para movimientos bancarios centrales."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from agente_comprobantes.control_financiero.auditoria_importacion import (
    normalizar_referencia_para_busqueda,
)
from agente_comprobantes.control_financiero.movimientos_centrales import (
    MovimientoBancarioCentral,
)


def clave_movimiento(movimiento: MovimientoBancarioCentral) -> tuple[str, str, str]:
    return (
        movimiento.banco.casefold().strip(),
        normalizar_referencia_para_busqueda(movimiento.referencia),
        movimiento.moneda.value,
    )


class RepositorioMovimientosCentrales:
    VERSION = 2

    def __init__(self, ruta: str | Path) -> None:
        self.ruta = Path(ruta).expanduser().resolve()

    def listar(self) -> list[MovimientoBancarioCentral]:
        if not self.ruta.exists():
            return []
        datos = json.loads(self.ruta.read_text(encoding="utf-8"))
        if not isinstance(datos, dict) or datos.get("version") not in (1, 2):
            raise ValueError("El registro bancario tiene un formato inválido.")
        if not isinstance(datos.get("movimientos"), list):
            raise ValueError("El registro bancario no contiene movimientos válidos.")

        if datos["version"] == 1:
            movimientos = [
                MovimientoBancarioCentral.model_validate(item)
                for item in datos["movimientos"]
            ]
        else:
            aplicaciones = datos.get("aplicaciones")
            if not isinstance(aplicaciones, list):
                raise ValueError("El registro no contiene aplicaciones válidas.")
            por_movimiento: dict[str, list[dict]] = {}
            claves: set[tuple[str, str]] = set()
            for item in aplicaciones:
                if not isinstance(item, dict):
                    raise ValueError("Existe una aplicación bancaria inválida.")
                identificador = item.get("movimiento_id")
                expediente = item.get("expediente")
                if not isinstance(identificador, str) or not isinstance(expediente, str):
                    raise ValueError("La aplicación requiere movimiento y expediente.")
                clave = (identificador, expediente.casefold())
                if clave in claves:
                    raise ValueError("La aplicación de una factura está duplicada.")
                claves.add(clave)
                por_movimiento.setdefault(identificador, []).append({
                    "expediente": expediente,
                    "importe": item.get("importe"),
                })
            movimientos = []
            for item in datos["movimientos"]:
                if not isinstance(item, dict) or "aplicaciones" in item:
                    raise ValueError("Los movimientos y sus aplicaciones deben estar separados.")
                identificador = item.get("identificador")
                movimientos.append(MovimientoBancarioCentral.model_validate({
                    **item,
                    "aplicaciones": por_movimiento.pop(identificador, []),
                }))
            if por_movimiento:
                raise ValueError("Hay aplicaciones huérfanas sin movimiento bancario.")
        self._validar_unicidad(movimientos)
        return movimientos

    def obtener(self, identificador: str) -> MovimientoBancarioCentral | None:
        return next(
            (item for item in self.listar() if item.identificador == identificador),
            None,
        )

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
        self._guardar([*actuales, movimiento], huella_esperada)

    def actualizar(
        self,
        movimiento: MovimientoBancarioCentral,
        *,
        huella_esperada: str,
    ) -> None:
        if self.huella() != huella_esperada:
            raise ValueError("El registro bancario cambió; vuelve a revisar.")
        actuales = self.listar()
        for indice, existente in enumerate(actuales):
            if existente.identificador == movimiento.identificador:
                actuales[indice] = movimiento
                self._guardar(actuales, huella_esperada)
                return
        raise ValueError("El movimiento bancario central ya no existe.")

    def _guardar(
        self,
        movimientos: list[MovimientoBancarioCentral],
        huella_esperada: str,
    ) -> None:
        """Escribe versión 2; migra v1 solo cuando hay un guardado válido."""
        if self.huella() != huella_esperada:
            raise ValueError("El registro bancario cambió; vuelve a revisar.")
        self._validar_unicidad(movimientos)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        registros: list[dict] = []
        aplicaciones: list[dict] = []
        for movimiento in movimientos:
            datos = movimiento.model_dump(mode="json")
            for aplicacion in datos.pop("aplicaciones"):
                aplicaciones.append({
                    "movimiento_id": movimiento.identificador,
                    **aplicacion,
                })
            registros.append(datos)
        payload = {
            "version": self.VERSION,
            "movimientos": registros,
            "aplicaciones": aplicaciones,
        }
        temporal: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                prefix=".movimientos_",
                suffix=".tmp",
                dir=self.ruta.parent,
                delete=False,
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

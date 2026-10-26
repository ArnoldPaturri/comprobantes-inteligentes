"""Adjuntos locales de control financiero: escritura por huella y lectura segura.

La referencia guarda únicamente un SHA-256 y extensión validada. No se
utilizan nombres enviados por el navegador para construir rutas de escritura.
"""

from __future__ import annotations

import hashlib
import io
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

MAX_BYTES = 8 * 1024 * 1024
REFERENCIA = re.compile(r"^adjunto:([a-f0-9]{64})\.(pdf|png|jpg)$")
EXTENSIONES = {"pdf", "png", "jpg", "jpeg"}


@dataclass(frozen=True, slots=True)
class ArchivoPreparado:
    nombre_original: str
    contenido: bytes
    extension: str
    huella: str

    @property
    def referencia(self) -> str:
        return f"adjunto:{self.huella}.{self.extension}"


def preparar_adjunto(nombre: str, contenido: bytes) -> ArchivoPreparado:
    """Valida bytes, extensión real, formato y tamaño antes de guardarlos."""
    if not isinstance(contenido, bytes) or not 0 < len(contenido) <= MAX_BYTES:
        raise ValueError("El archivo debe tener entre 1 byte y 8 MB.")
    if not nombre or "/" in nombre or "\\" in nombre:
        raise ValueError("El nombre de archivo recibido no es válido.")
    extension = Path(nombre).suffix.lower().lstrip(".")
    if extension not in EXTENSIONES:
        raise ValueError("Solo se admiten archivos PDF, PNG o JPG.")
    if contenido.startswith(b"%PDF-"):
        detectado = "pdf"
        if b"%%EOF" not in contenido[-2048:]:
            raise ValueError("El PDF parece estar incompleto.")
    elif contenido.startswith(b"\x89PNG\r\n\x1a\n"):
        detectado = "png"
    elif contenido.startswith(b"\xff\xd8\xff"):
        detectado = "jpg"
    else:
        raise ValueError("La firma del archivo no corresponde a PDF, PNG o JPG.")

    if extension == "jpeg":
        extension = "jpg"
    if detectado != extension:
        raise ValueError("La extensión y el contenido real del archivo no coinciden.")
    if detectado != "pdf":
        try:
            with Image.open(io.BytesIO(contenido)) as imagen:
                imagen.verify()
        except (OSError, SyntaxError, ValueError, UnidentifiedImageError) as exc:
            raise ValueError("La imagen está dañada o no es válida.") from exc

    return ArchivoPreparado(
        nombre_original=nombre,
        contenido=contenido,
        extension=extension,
        huella=hashlib.sha256(contenido).hexdigest(),
    )


class AlmacenAdjuntos:
    """Almacén inmutable junto al Excel activo, excluido del repositorio Git."""

    def __init__(self, directorio: str | Path) -> None:
        self._directorio = Path(directorio).expanduser().resolve()

    def guardar(self, archivo: ArchivoPreparado) -> str:
        """Almacena una única copia por hash con nombre controlado."""
        destino = self._directorio / archivo.referencia.removeprefix("adjunto:")
        if destino.is_file():
            if destino.read_bytes() != archivo.contenido:
                raise ValueError("El adjunto existente no coincide con su huella.")
            return archivo.referencia

        self._directorio.mkdir(parents=True, exist_ok=True)
        temporal: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=".temporal_",
                dir=self._directorio,
                delete=False,
            ) as stream:
                temporal = stream.name
                stream.write(archivo.contenido)
                stream.flush()
                os.fsync(stream.fileno())
            if destino.exists():
                raise ValueError("El destino ya existe y no se debe sobrescribir.")
            os.replace(temporal, destino)
        finally:
            if temporal is not None and os.path.exists(temporal):
                os.unlink(temporal)
        return archivo.referencia

    def abrir(self, referencia: str) -> tuple[bytes, str]:
        """Solo abre adjuntos internos; rechaza rutas arbitrarias y cambios de bytes."""
        coincidencia = REFERENCIA.fullmatch(referencia)
        if coincidencia is None:
            raise ValueError("Solo se pueden abrir adjuntos guardados por el sistema.")
        huella, extension = coincidencia.groups()
        ruta = self._directorio / f"{huella}.{extension}"
        if not ruta.is_file() or ruta.is_symlink():
            raise FileNotFoundError("No se encontró el adjunto en el almacén local.")
        contenido = ruta.read_bytes()
        if len(contenido) > MAX_BYTES or hashlib.sha256(contenido).hexdigest() != huella:
            raise ValueError("La integridad del adjunto no se pudo verificar.")
        return contenido, extension


def almacen_para_excel(ruta_excel: str | Path) -> AlmacenAdjuntos:
    """Siempre en una carpeta hermana del Excel: sin modificar el libro."""
    return AlmacenAdjuntos(Path(ruta_excel).resolve().parent / "adjuntos_financieros")

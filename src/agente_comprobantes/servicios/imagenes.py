from __future__ import annotations

import base64
import hashlib
import io
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from agente_comprobantes.configuracion import Configuracion
from agente_comprobantes.excepciones import ErrorValidacionImagen

SUPPORTED_FORMATS = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
    "GIF": "image/gif",
    "BMP": "image/bmp",
    "TIFF": "image/tiff",
}

@dataclass(frozen=True, slots=True)
class ImagenPreparada:
    source_name: str
    data_url: str
    original_sha256: str
    content_sha256: str
    payload_bytes: int


@dataclass(frozen=True, slots=True)
class DocumentoPreparado:
    images: tuple[ImagenPreparada, ...]
    source_hash: str

    @property
    def source_names(self) -> list[str]:
        return [image.source_name for image in self.images]

    @property
    def total_payload_bytes(self) -> int:
        return sum(image.payload_bytes for image in self.images)


class ServicioImagenes:
    def __init__(self, settings: Configuracion) -> None:
        self._settings = settings

    def prepare(self, paths: Iterable[str | Path]) -> DocumentoPreparado:
        image_paths = [Path(path).expanduser().resolve() for path in paths]
        if not image_paths:
            raise ErrorValidacionImagen("Debes proporcionar al menos una imagen.")
        if len(image_paths) > self._settings.max_images_per_document:
            raise ErrorValidacionImagen(
                f"Máximo {self._settings.max_images_per_document} imágenes por documento."
            )

        prepared = tuple(self._prepare_one(path) for path in image_paths)
        max_bytes = self._settings.max_payload_mb * 1024 * 1024
        total_bytes = sum(image.payload_bytes for image in prepared)
        if total_bytes > max_bytes:
            raise ErrorValidacionImagen(
                f"Las imágenes procesadas pesan {total_bytes / 1024 / 1024:.2f} MB; "
                f"el máximo es {self._settings.max_payload_mb} MB."
            )

        combined = hashlib.sha256()
        for image in prepared:
            combined.update(image.content_sha256.encode("ascii"))
        return DocumentoPreparado(images=prepared, source_hash=combined.hexdigest())

    
    @staticmethod
    def _convert_to_rgb(image: Image.Image) -> Image.Image:
        has_transparency = (
            image.mode in {"RGBA", "LA"}
            or "transparency" in image.info
        )

        if not has_transparency:
            return image.convert("RGB")

        rgba_image = image.convert("RGBA")
        background = Image.new(
            "RGB",
            rgba_image.size,
            color="white",
        )
        background.paste(
            rgba_image,
            mask=rgba_image.getchannel("A"),
        )
        return background
    
    
    def _resize_for_ocr(self, image: Image.Image) -> Image.Image:
        width, height = image.size
        max_width = self._settings.image_max_width
        max_height = self._settings.image_max_height

        scale = min(
            max_width / width,
            max_height / height,
        )

        if scale > 1:
            scale = min(scale, 2.0)

        if abs(scale - 1) < 0.01:
            return image

        new_size = (
            max(1, round(width * scale)),
            max(1, round(height * scale)),
        )
        return image.resize(
            new_size,
            Image.Resampling.LANCZOS,
        )

    
    def _prepare_one(self, path: Path) -> ImagenPreparada:
        if not path.is_file():
            raise ErrorValidacionImagen(f"No existe la imagen: {path}")

        original = path.read_bytes()
        original_hash = hashlib.sha256(original).hexdigest()
        try:
            with Image.open(io.BytesIO(original)) as opened:
                source_format = (opened.format or "").upper()
                if source_format not in SUPPORTED_FORMATS:
                    raise ErrorValidacionImagen(
                        f"Formato no soportado en {path.name}: {source_format or 'desconocido'}."
                    )
                
                frame_count = getattr(opened, "n_frames", 1)
                if frame_count > 1:
                    raise ErrorValidacionImagen(
                        f"{path.name} contiene {frame_count} cuadros o páginas. "
                        "Por ahora debes separarlos en archivos individuales."
                    )

                image = ImageOps.exif_transpose(opened)
                image = self._convert_to_rgb(image)
                if getattr(image, "is_animated", False):
                    image.seek(0)
                image = image.convert("RGB")
                image = self._resize_for_ocr(image)

                output = io.BytesIO()

                if source_format == "JPEG":
                    output_mime_type = "image/jpeg"
                    image.save(
                        output,
                        format="JPEG",
                        quality=self._settings.jpeg_quality,
                        optimize=True,
                        progressive=True,
                    )
                else:
                    output_mime_type = "image/png"
                    image.save(
                        output,
                        format="PNG",
                        optimize=True,
                    )              
        except (
            UnidentifiedImageError,
            OSError,
            Image.DecompressionBombError,
        ) as exc:
        
            raise ErrorValidacionImagen(f"Imagen inválida o dañada: {path.name}") from exc

        payload = output.getvalue()
        content_hash = hashlib.sha256(payload).hexdigest()
        encoded = base64.b64encode(payload).decode("ascii")
        return ImagenPreparada(
            source_name=path.name,
            data_url=f"data:{output_mime_type};base64,{encoded}",
            original_sha256=original_hash,
            content_sha256=content_hash,
            payload_bytes=len(payload),
        )

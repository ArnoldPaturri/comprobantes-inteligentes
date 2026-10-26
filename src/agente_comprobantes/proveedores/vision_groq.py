from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from agente_comprobantes.configuracion import Configuracion
from agente_comprobantes.dominio import ExtraccionDocumento, TipoDocumento
from agente_comprobantes.excepciones import ErrorExtraccion
from agente_comprobantes.prompts import EXTRACTION_SCHEMA, crear_prompt_extraccion
from agente_comprobantes.proveedores.base import ProveedorVision
from agente_comprobantes.proveedores.parseo import parsear_objeto_json
from agente_comprobantes.servicios.imagenes import DocumentoPreparado

MAX_GROQ_IMAGES = 3


def _schema_without_formats(value: Any) -> Any:
    """Elimina formatos no esenciales del esquema usado por Groq."""

    if isinstance(value, dict):
        return {
            key: _schema_without_formats(item)
            for key, item in value.items()
            if key != "format"
        }

    if isinstance(value, list):
        return [_schema_without_formats(item) for item in value]

    return value


GROQ_EXTRACTION_SCHEMA = _schema_without_formats(
    deepcopy(EXTRACTION_SCHEMA)
)


class ProveedorVisionGroq(ProveedorVision):
    """Adaptador de visión para Qwen mediante Groq."""

    def __init__(
        self,
        settings: Configuracion,
        client: Any | None = None,
    ) -> None:
        self._settings = settings

        if client is None:
            try:
                from groq import Groq
            except ImportError as exc:  # pragma: no cover
                raise ErrorExtraccion(
                    "No está instalado el SDK de Groq. "
                    "Ejecuta pip install -r requirements.txt."
                ) from exc

            client = Groq(
                api_key=settings.exigir_clave_groq(),
                timeout=settings.groq_timeout_seconds,
                max_retries=0,
            )

        self._client = client

    def extraer(
        self,
        document: DocumentoPreparado,
        expected_type: TipoDocumento,
    ) -> ExtraccionDocumento:
        if len(document.images) > MAX_GROQ_IMAGES:
            raise ErrorExtraccion(
                "Groq admite como máximo 3 imágenes por solicitud. "
                "Este documento debe procesarse con Cohere."
            )

        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": crear_prompt_extraccion(
                    expected_type,
                    len(document.images),
                ),
            }
        ]

        content.extend(
            {
                "type": "image_url",
                "image_url": {
                    "url": image.data_url,
                },
            }
            for image in document.images
        )

        raw_text: str | None = None

        try:
            response = self._client.chat.completions.create(
                model=self._settings.groq_model,
                messages=[
                    {
                        "role": "user",
                        "content": content,
                    }
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "document_extraction",
                        "strict": True,
                        "schema": GROQ_EXTRACTION_SCHEMA,
                    },
                },
                reasoning_effort="none",
                temperature=0.1,
                top_p=0.8,
                max_completion_tokens=1800,
            )

            raw_text = self._response_text(response)
            payload = parsear_objeto_json(raw_text)

            return ExtraccionDocumento.model_validate(payload)

        except json.JSONDecodeError as exc:
            diagnostic_path = self._save_diagnostic(raw_text, exc)
            raise ErrorExtraccion(
                "Groq devolvió texto que no es un JSON válido. "
                f"Diagnóstico guardado en: {diagnostic_path}"
            ) from exc

        except ValidationError as exc:
            diagnostic_path = self._save_diagnostic(raw_text, exc)
            details = self._validation_summary(exc)
            raise ErrorExtraccion(
                "El JSON de Groq contiene valores inesperados: "
                f"{details}. Diagnóstico guardado en: {diagnostic_path}"
            ) from exc

        except ErrorExtraccion:
            raise

        except Exception as exc:
            status_code = getattr(exc, "status_code", None)
            error_name = exc.__class__.__name__

            if status_code is not None:
                detail = f"HTTP {status_code} ({error_name})"
            else:
                detail = error_name

            raise ErrorExtraccion(
                f"No se pudo extraer el documento con Groq: {detail}"
            ) from exc

    @staticmethod
    def _response_text(response: Any) -> str:
        try:
            text = response.choices[0].message.content
        except (AttributeError, IndexError, TypeError) as exc:
            raise ErrorExtraccion(
                "Groq devolvió una respuesta inesperada."
            ) from exc

        if not text:
            raise ErrorExtraccion(
                "Groq devolvió una respuesta vacía."
            )

        return str(text)

    def _save_diagnostic(
        self,
        raw_text: str | None,
        exc: Exception,
    ) -> Path:
        directory = self._settings.ruta_diagnosticos()
        directory.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = directory / f"groq_failure_{timestamp}.json"

        payload = {
            "timestamp": datetime.now().isoformat(
                timespec="seconds"
            ),
            "provider": "groq",
            "model": self._settings.groq_model,
            "error_type": exc.__class__.__name__,
            "error": str(exc),
            "raw_response": raw_text,
        }

        path.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        return path

    @staticmethod
    def _validation_summary(
        exc: ValidationError,
    ) -> str:
        details: list[str] = []

        for error in exc.errors(include_url=False)[:3]:
            ubicacion = error.get("loc", ())
            field = ".".join(
                str(part) for part in ubicacion
            ) or "respuesta"

            details.append(
                f"{field}: "
                f"{error.get('msg', 'valor inválido')}"
            )

        return (
            "; ".join(details)
            or "error de validación no especificado"
        )
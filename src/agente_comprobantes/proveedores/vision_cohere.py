from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from agente_comprobantes.configuracion import Configuracion
from agente_comprobantes.dominio import ExtraccionDocumento, TipoDocumento
from agente_comprobantes.excepciones import ErrorExtraccion
from agente_comprobantes.prompts import EXTRACTION_SCHEMA, build_extraction_prompt
from agente_comprobantes.proveedores.base import ProveedorVision
from agente_comprobantes.proveedores.parseo import parse_json_object
from agente_comprobantes.servicios.imagenes import DocumentoPreparado


class ProveedorVisionCohere(ProveedorVision):
    """Adaptador para Command A Vision mediante Chat API V2."""

    RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}

    def __init__(self, settings: Configuracion, client: Any | None = None) -> None:
        self._settings = settings
        if client is None:
            try:
                import cohere
            except ImportError as exc:  # pragma: no cover - depende del entorno
                raise ErrorExtraccion(
                    "No está instalado el SDK de Cohere. Ejecuta pip install -r requirements.txt."
                ) from exc
            client = cohere.ClientV2(
                api_key=settings.require_cohere_api_key(),
                timeout=settings.request_timeout_seconds,
            )
        self._client = client

    def extract(
        self,
        document: DocumentoPreparado,
        expected_type: TipoDocumento,
    ) -> ExtraccionDocumento:
        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": build_extraction_prompt(expected_type, len(document.images)),
            }
        ]
        content.extend(
            {
                "type": "image_url",
                "image_url": {
                    "url": image.data_url,
                    "detail": self._settings.image_detail,
                },
            }
            for image in document.images
        )

        last_error: Exception | None = None
        for attempt in range(1, self._settings.max_api_attempts + 1):
            raw_text: str | None = None
            try:
                response = self._client.chat(
                    model=self._settings.cohere_model,
                    messages=[{"role": "user", "content": content}],
                    response_format={"type": "json_object", "schema": EXTRACTION_SCHEMA},
                    temperature=0,
                    max_tokens=1800,
                )
                raw_text = self._response_text(response)
                payload = parse_json_object(raw_text)
                return ExtraccionDocumento.model_validate(payload)
            except json.JSONDecodeError as exc:
                diagnostic_path = self._save_diagnostic(raw_text, exc)
                raise ErrorExtraccion(
                    "Cohere devolvió texto que no es un JSON válido. "
                    f"Diagnóstico guardado en: {diagnostic_path}"
                ) from exc
            except ValidationError as exc:
                diagnostic_path = self._save_diagnostic(raw_text, exc)
                details = self._validation_summary(exc)
                raise ErrorExtraccion(
                    "El JSON de Cohere contiene valores con formato inesperado: "
                    f"{details}. Diagnóstico guardado en: {diagnostic_path}"
                ) from exc
            except Exception as exc:  # SDK puede exponer clases distintas por versión
                last_error = exc
                if attempt >= self._settings.max_api_attempts or not self._is_retryable(exc):
                    break
                time.sleep(min(2 ** (attempt - 1), 8))

        message = self._safe_error_message(last_error)
        raise ErrorExtraccion(
            f"No se pudo extraer el documento con Cohere: {message}"
        ) from last_error

    @staticmethod
    def _response_text(response: Any) -> str:
        try:
            content = response.message.content
            if not content:
                raise ValueError("respuesta sin contenido")
            block = content[0]
            text = block.text if hasattr(block, "text") else block.get("text")
            if not text:
                raise ValueError("bloque sin texto")
            return str(text)
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise ErrorExtraccion("Respuesta vacía o inesperada del proveedor.") from exc

    @staticmethod
    def _save_diagnostic(self, raw_text: str | None, exc: Exception) -> Path:
        directory = self._settings.resolved_diagnostics_dir()
        directory.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = directory / f"cohere_failure_{timestamp}.json"
        payload = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "error_type": exc.__class__.__name__,
            "error": str(exc),
            "raw_response": raw_text,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    @staticmethod
    def _validation_summary(exc: ValidationError) -> str:
        details: list[str] = []
        for error in exc.errors(include_url=False)[:3]:
            field = ".".join(str(part) for part in error.get("loc", ())) or "respuesta"
            details.append(f"{field}: {error.get('msg', 'valor inválido')}")
        return "; ".join(details) or "error de validación no especificado"

    @classmethod
    def _is_retryable(cls, exc: Exception) -> bool:
        status_code = getattr(exc, "status_code", None)
        if status_code in cls.RETRYABLE_STATUS_CODES:
            return True
        name = exc.__class__.__name__.lower()
        return any(token in name for token in ("timeout", "ratelimit", "connection"))

    @staticmethod
    def _safe_error_message(exc: Exception | None) -> str:
        if exc is None:
            return "error desconocido"
        status_code = getattr(exc, "status_code", None)
        if status_code:
            return f"HTTP {status_code} ({exc.__class__.__name__})"
        return exc.__class__.__name__

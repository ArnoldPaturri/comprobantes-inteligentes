from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Priorizar registros ya existentes al migrar desde la estructura antigua.
ARCHIVO_ANTERIOR = PROJECT_ROOT / "output" / "registros.xlsx"
ARCHIVO_NUEVO = PROJECT_ROOT / "salida" / "registros.xlsx"


class Settings(BaseSettings):
    """Configuración central leída desde variables de entorno o ``.env``."""

    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    vision_provider: Literal["auto", "cohere", "groq"] = "auto"

    groq_api_key: SecretStr | None = None
    groq_model: str = "qwen/qwen3.8-27b"
    groq_timeout_seconds: float = Field(default=60.0, gt=0, le=300)

    cohere_api_key: SecretStr | None = None
    cohere_model: str = "command-a-vision-07-2025"
    image_detail: Literal["low", "high", "auto"] = "high"
    workbook_path: Path = ARCHIVO_ANTERIOR if ARCHIVO_ANTERIOR.is_file() else ARCHIVO_NUEVO
    diagnostics_dir: Path = PROJECT_ROOT / "salida" / "diagnosticos"

    max_images_per_document: int = Field(default=20, ge=1, le=20)
    max_payload_mb: int = Field(default=20, ge=1, le=20)
    image_max_width: int = Field(default=1536, ge=512)
    image_max_height: int = Field(default=2048, ge=512)
    jpeg_quality: int = Field(default=90, ge=70, le=95)

    min_extraction_confidence: float = Field(default=0.75, ge=0, le=1)
    supplier_similarity_threshold: float = Field(default=0.82, ge=0, le=1)
    request_timeout_seconds: float = Field(default=90.0, gt=0)
    max_api_attempts: int = Field(default=3, ge=1, le=5)

    def resolved_workbook_path(self) -> Path:
        path = self.workbook_path.expanduser()
        return path if path.is_absolute() else PROJECT_ROOT / path

    def resolved_diagnostics_dir(self) -> Path:
        path = self.diagnostics_dir.expanduser()
        return path if path.is_absolute() else PROJECT_ROOT / path

    def has_cohere_api_key(self) -> bool:
        return bool(
            self.cohere_api_key
            and self.cohere_api_key.get_secret_value().strip()
        )

    def has_groq_api_key(self) -> bool:
        return bool(
            self.groq_api_key
            and self.groq_api_key.get_secret_value().strip()
        )

    def require_cohere_api_key(self) -> str:
        if not self.has_cohere_api_key():
            raise ValueError(
                "Falta COHERE_API_KEY. Copia .env.example como .env y agrega tu clave."
            )

        assert self.cohere_api_key is not None
        return self.cohere_api_key.get_secret_value()


    def require_groq_api_key(self) -> str:
        if not self.has_groq_api_key():
            raise ValueError(
                "Falta GROQ_API_KEY. Agrega tu clave de Groq en el archivo .env."
            )

        assert self.groq_api_key is not None
        return self.groq_api_key.get_secret_value()

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

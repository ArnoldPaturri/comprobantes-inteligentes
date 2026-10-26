from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from invoice_agent.config import Settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        workbook_path=tmp_path / "registros.xlsx",
        min_extraction_confidence=0.75,
        supplier_similarity_threshold=0.82,
    )


@pytest.fixture
def make_image(tmp_path: Path):
    counter = 0

    def factory(name: str | None = None, color: str = "white", text: str = "Documento") -> Path:
        nonlocal counter
        counter += 1
        path = tmp_path / (name or f"image-{counter}.png")
        image = Image.new("RGB", (900, 1200), color=color)
        draw = ImageDraw.Draw(image)
        draw.text((50, 50), f"{text}-{counter}", fill="black")
        image.save(path)
        return path

    return factory


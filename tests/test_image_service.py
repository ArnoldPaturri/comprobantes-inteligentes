import base64

import pytest

from invoice_agent.exceptions import ImageValidationError
from invoice_agent.services.image_service import ImageService


def test_prepares_multiple_images_as_one_document(settings, make_image) -> None:
    first = make_image("page-1.png", text="Página 1")
    second = make_image("page-2.png", color="lightgray", text="Página 2")

    result = ImageService(settings).prepare([first, second])

    assert result.source_names == ["page-1.png", "page-2.png"]
    assert len(result.images) == 2
    assert len(result.source_hash) == 64
    first_image = result.images[0]
    assert first_image.data_url.startswith("data:image/png;base64,")
    encoded = first_image.data_url.split(",", 1)[1]
    decoded = base64.b64decode(encoded)

    assert decoded.startswith(b"\x89PNG\r\n\x1a\n")


def test_rejects_missing_image(settings) -> None:
    with pytest.raises(ImageValidationError, match="No existe"):
        ImageService(settings).prepare(["does-not-exist.png"])


def test_rejects_more_than_twenty_images(settings, make_image) -> None:
    images = [make_image(name=f"{index}.png") for index in range(21)]

    with pytest.raises(ImageValidationError, match="Máximo 20"):
        ImageService(settings).prepare(images)


def test_keeps_jpeg_output_for_jpeg_source(settings, make_image) -> None:
    source = make_image(
        "payment.jpg",
        text="Monto: 30 117.62",
    )

    result = ImageService(settings).prepare([source])

    prepared_image = result.images[0]

    assert prepared_image.data_url.startswith("data:image/jpeg;base64,")

    encoded = prepared_image.data_url.split(",", 1)[1]
    decoded = base64.b64decode(encoded)

    assert decoded.startswith(b"\xff\xd8")
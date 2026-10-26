import base64

import pytest

from agente_comprobantes.excepciones import ErrorValidacionImagen
from agente_comprobantes.servicios.imagenes import ServicioImagenes


def test_prepares_multiple_images_as_one_document(settings, make_image) -> None:
    first = make_image("page-1.png", text="Página 1")
    second = make_image("page-2.png", color="lightgray", text="Página 2")

    result = ServicioImagenes(settings).preparar([first, second])

    assert result.nombres_archivos == ["page-1.png", "page-2.png"]
    assert len(result.images) == 2
    assert len(result.source_hash) == 64
    first_image = result.images[0]
    assert first_image.data_url.startswith("data:image/png;base64,")
    encoded = first_image.data_url.split(",", 1)[1]
    decoded = base64.b64decode(encoded)

    assert decoded.startswith(b"\x89PNG\r\n\x1a\n")


def test_rejects_missing_image(settings) -> None:
    with pytest.raises(ErrorValidacionImagen, match="No existe"):
        ServicioImagenes(settings).preparar(["does-not-exist.png"])


def test_rejects_more_than_twenty_images(settings, make_image) -> None:
    images = [make_image(name=f"{index}.png") for index in range(21)]

    with pytest.raises(ErrorValidacionImagen, match="Máximo 20"):
        ServicioImagenes(settings).preparar(images)


def test_keeps_jpeg_output_for_jpeg_source(settings, make_image) -> None:
    source = make_image(
        "payment.jpg",
        text="Monto: 30 117.62",
    )

    result = ServicioImagenes(settings).preparar([source])

    prepared_image = result.images[0]

    assert prepared_image.data_url.startswith("data:image/jpeg;base64,")

    encoded = prepared_image.data_url.split(",", 1)[1]
    decoded = base64.b64decode(encoded)

    assert decoded.startswith(b"\xff\xd8")
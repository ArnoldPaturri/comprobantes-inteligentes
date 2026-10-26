"""Seguridad, persistencia e integridad de adjuntos de control financiero."""

import hashlib
from io import BytesIO

import pytest
from PIL import Image

from agente_comprobantes.control_financiero.archivos import (
    AlmacenAdjuntos,
    almacen_para_excel,
    preparar_adjunto,
)


def imagen_png() -> bytes:
    stream = BytesIO()
    Image.new("RGB", (8, 8)).save(stream, format="PNG")
    return stream.getvalue()


def test_adjunto_png_real_se_guarda_y_recupera(tmp_path) -> None:
    datos = imagen_png()
    prep = preparar_adjunto("voucher.png", datos)
    almacen = AlmacenAdjuntos(tmp_path / "archivos")
    ref = almacen.guardar(prep)
    assert ref.startswith("adjunto:")
    assert almacen.abrir(ref) == (datos, "png")
    assert almacen.guardar(prep) == ref
    assert len(list((tmp_path / "archivos").iterdir())) == 1


def test_adjunto_pdf_guardado_sin_tocar_excel(tmp_path) -> None:
    libro = tmp_path / "registros.xlsx"
    libro.write_bytes(b"excel-original")
    datos = b"%PDF-1.4\n1 0 obj\nendobj\n%%EOF\n"
    prep = preparar_adjunto("constancia.pdf", datos)
    almacen = almacen_para_excel(libro)
    ref = almacen.guardar(prep)
    assert almacen.abrir(ref) == (datos, "pdf")
    assert libro.read_bytes() == b"excel-original"


@pytest.mark.parametrize(
    ("nombre", "datos"),
    [
        ("fake.pdf", b"GIF89a"),
        ("imagen.jpg", b"%PDF-1.4\n%%EOF"),
        ("../malicioso.png", b"hola"),
        ("pagina.html", b"<html></html>"),
        ("vacio.pdf", b""),
        ("enorme.pdf", b"%PDF-1.4" + b"A" * (8 * 1024 * 1024)),
        ("truncado.pdf", b"%PDF-1.4\ncontenido sin final"),
        ("corrupto.png", b"\x89PNG\r\n\x1a\ncorrupto"),
    ],
)
def test_rechazar_archivos_que_no_son_admisibles(nombre: str, datos: bytes) -> None:
    with pytest.raises(ValueError):
        preparar_adjunto(nombre, datos)


@pytest.mark.parametrize(
    "referencia",
    [
        "../.env",
        "/etc/passwd",
        "voucher.png",
        "adjunto:../../registros.xlsx",
        "adjunto:aaa.pdf",
    ],
)
def test_lectura_no_admite_rutas_ajenas(tmp_path, referencia: str) -> None:
    with pytest.raises(ValueError):
        AlmacenAdjuntos(tmp_path).abrir(referencia)


def test_detecta_manipulacion_de_adjunto(tmp_path) -> None:
    datos = imagen_png()
    almacen = AlmacenAdjuntos(tmp_path)
    ref = almacen.guardar(preparar_adjunto("archivo.png", datos))
    (tmp_path / ref.removeprefix("adjunto:")).write_bytes(b"alterado")
    with pytest.raises(ValueError, match="integridad"):
        almacen.abrir(ref)


def test_referencia_es_hash_y_no_nombre_suministrado() -> None:
    datos = imagen_png()
    preparado = preparar_adjunto("recibo.png", datos)
    assert preparado.referencia == f"adjunto:{hashlib.sha256(datos).hexdigest()}.png"

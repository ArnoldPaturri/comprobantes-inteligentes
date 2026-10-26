from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol
from uuid import uuid4


class UploadedFileLike(Protocol):
    name: str

    def getvalue(self) -> bytes: ...


def _safe_filename(filename: str) -> str:
    path = Path(filename)
    safe_stem = re.sub(
        r"[^A-Za-z0-9._-]+",
        "_",
        path.stem,
    ).strip("._")

    if not safe_stem:
        safe_stem = "image"

    return f"{safe_stem[:80]}{path.suffix.lower()}"


def save_uploaded_files(
    uploaded_files: Iterable[UploadedFileLike],
    root: Path = Path("entrada/cargas"),
) -> list[str]:
    files = list(uploaded_files)

    if not files:
        raise ValueError(
            "Debes proporcionar al menos una imagen."
        )

    batch_directory = root / uuid4().hex
    batch_directory.mkdir(
        parents=True,
        exist_ok=False,
    )

    stored_paths: list[str] = []

    for index, uploaded_file in enumerate(files, start=1):
        filename = (
            f"{index:02d}_"
            f"{_safe_filename(uploaded_file.name)}"
        )
        destination = batch_directory / filename
        destination.write_bytes(uploaded_file.getvalue())
        stored_paths.append(str(destination.resolve()))

    return stored_paths
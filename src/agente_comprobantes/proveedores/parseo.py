from __future__ import annotations

import json
from typing import Any


def parsear_objeto_json(raw_text: str) -> dict[str, Any]:
    text = raw_text.strip()

    if text.startswith("```"):
        lines = text.splitlines()

        if lines and lines[0].strip().lower() in {"```", "```json"}:
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")

        if start < 0 or end <= start:
            raise

        payload = json.loads(text[start : end + 1])

    if not isinstance(payload, dict):
        raise json.JSONDecodeError(
            "La respuesta JSON no es un objeto",
            text,
            0,
        )

    properties = payload.get("properties")

    if (
        payload.get("type") == "object"
        and isinstance(properties, dict)
        and "document_type" in properties
    ):
        payload = properties

    return payload
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


MISSING_TEXT_VALUES = {"", "NULL", "NONE", "N/A", "NA", "NO APLICA", "NO VISIBLE"}

ILLEGAL_CONTROL_CHARACTER_PATTERN = re.compile(
    r"[\x00-\x08\x0B-\x0C\x0E-\x1F]"
)

def _sanitize_text(value: Any) -> str:
    return ILLEGAL_CONTROL_CHARACTER_PATTERN.sub(
        "",
        str(value),
    ).strip()


PROVIDER_LABEL_PATTERN = re.compile(
    r"^\s*(?:"
    r"GIRADO|"
    r"BENEFICIARIO|"
    r"PROVEEDOR|"
    r"DESTINATARIO|"
    r"EMISOR|"
    r"RAZ[ÓO]N\s+SOCIAL|"
    r"A\s+FAVOR\s+DE"
    r")\s*[:=]\s*",
    re.IGNORECASE,
)


def _is_missing(value: Any) -> bool:
    if value is None or value == {} or value == []:
        return True
    return isinstance(value, str) and value.strip().upper() in MISSING_TEXT_VALUES


def _parse_decimal(value: Any) -> Decimal | None:
    if _is_missing(value):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))

    text = str(value).strip().upper()
    for token in ("S/", "PEN", "US$", "USD", "$", " "):
        text = text.replace(token, "")
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        decimal_part = text.rsplit(",", 1)[-1]
        text = text.replace(",", ".") if len(decimal_part) <= 2 else text.replace(",", "")
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"Monto inválido: {value!r}") from exc


def _parse_date(value: Any) -> date | None:
    if _is_missing(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip().split("T", 1)[0]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Fecha inválida: {value!r}")

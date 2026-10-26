import re
import unicodedata

LEGAL_SUFFIXES = {
    "SAC",
    "SA",
    "SRL",
    "EIRL",
    "SAA",
    "SOCIEDAD",
    "ANONIMA",
    "CERRADA",
    "LIMITADA",
}


def normalizar_texto(value: str | None) -> str:
    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKD", value.upper())
    ascii_text = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return " ".join(re.sub(r"[^A-Z0-9]+", " ", ascii_text).split())


def normalizar_proveedor(value: str | None) -> str:
    tokens = [token for token in normalizar_texto(value).split() if token not in LEGAL_SUFFIXES]
    collapsed: list[str] = []
    initials = ""
    for token in tokens:
        if len(token) == 1:
            initials += token
            continue
        if initials:
            collapsed.append(initials)
            initials = ""
        collapsed.append(token)
    if initials:
        collapsed.append(initials)
    return " ".join(collapsed)

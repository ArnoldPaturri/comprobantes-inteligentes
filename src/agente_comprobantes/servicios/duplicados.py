from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from difflib import SequenceMatcher

from agente_comprobantes.dominio import (
    CoincidenciaDuplicado,
    ExtraccionDocumento,
    ReferenciaDocumento,
)
from agente_comprobantes.servicios.normalizacion_texto import normalize_supplier, normalize_text


class ServicioDuplicados:
    """Detecta coincidencias; nunca elimina registros automáticamente."""

    def find_matches(
        self,
        extraction: ExtraccionDocumento,
        source_hash: str,
        existing: list[ReferenciaDocumento],
    ) -> list[CoincidenciaDuplicado]:
        matches: list[CoincidenciaDuplicado] = []
        for candidate in existing:
            if candidate.document_type != extraction.document_type:
                continue
            score, reasons = self._score(extraction, source_hash, candidate)
            if score >= 0.75:
                matches.append(
                    CoincidenciaDuplicado(
                        document_id=candidate.document_id,
                        document_type=candidate.document_type,
                        score=round(score, 3),
                        reasons=reasons,
                    )
                )
        return sorted(matches, key=lambda item: item.score, reverse=True)

    def _score(
        self,
        extraction: ExtraccionDocumento,
        source_hash: str,
        candidate: ReferenciaDocumento,
    ) -> tuple[float, list[str]]:
        if source_hash == candidate.source_hash:
            return 1.0, ["Mismo contenido de imagen"]

        reasons: list[str] = []
        scores: list[float] = []
        left_number = normalize_text(extraction.document_number)
        right_number = normalize_text(candidate.document_number)

        if (
            extraction.provider_tax_id
            and candidate.provider_tax_id
            and extraction.provider_tax_id == candidate.provider_tax_id
            and left_number
            and left_number == right_number
        ):
            return 0.99, ["Mismo RUC y número de documento"]

        if left_number and left_number == right_number:
            scores.append(0.85)
            reasons.append("Mismo número de documento")

        if (
            extraction.operation_number
            and candidate.operation_number
            and normalize_text(extraction.operation_number)
            == normalize_text(candidate.operation_number)
        ):
            return 0.98, ["Mismo número de operación"]

        supplier_similarity = self._similarity(extraction.provider, candidate.provider)
        if supplier_similarity >= 0.9:
            scores.append(0.25)
            reasons.append("Proveedor coincidente")

        if self._same_amount(extraction.total_amount, candidate.amount):
            scores.append(0.25)
            reasons.append("Mismo monto")

        if extraction.document_date and candidate.document_date:
            if abs(extraction.document_date - candidate.document_date) <= timedelta(days=1):
                scores.append(0.2)
                reasons.append("Fecha igual o cercana")

        if extraction.currency and candidate.currency and extraction.currency == candidate.currency:
            scores.append(0.1)
            reasons.append("Misma moneda")

        concept_similarity = self._similarity(extraction.concept, candidate.concept)
        if concept_similarity >= 0.9:
            scores.append(0.1)
            reasons.append("Descripción similar")

        return min(sum(scores), 0.95), reasons

    @staticmethod
    def _similarity(left: str | None, right: str | None) -> float:
        normalized_left = normalize_supplier(left)
        normalized_right = normalize_supplier(right)
        if not normalized_left or not normalized_right:
            return 0.0
        return SequenceMatcher(None, normalized_left, normalized_right).ratio()

    @staticmethod
    def _same_amount(left: Decimal | None, right: Decimal | None) -> bool:
        return left is not None and right is not None and abs(left - right) <= Decimal("0.01")

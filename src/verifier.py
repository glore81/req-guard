"""Верификатор цитат: защита от галлюцинаций.
Каждая цитата дефекта должна дословно (с точностью до пробелов/регистра)
присутствовать в документе. Если ни одна цитата не найдена — дефект отбрасывается.
Заодно проставляет номер страницы каждой цитаты."""
from __future__ import annotations

import re

from .schema import Defect, Document, Quote


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def find_page(doc: Document, quote: str) -> int | None:
    q = _norm(quote)
    if not q:
        return None
    for i, page in enumerate(doc.pages, start=1):
        if q in _norm(page):
            return i
    return None


def verify(doc: Document, defects: list[Defect]) -> tuple[list[Defect], list[Defect]]:
    """Возвращает (подтверждённые, отброшенные).
    Дефект подтверждён, если хотя бы одна цитата найдена в документе.
    Ненайденные цитаты удаляются из списка."""
    ok, dropped = [], []
    for d in defects:
        verified_quotes: list[Quote] = []
        for q in d.quotes:
            page = find_page(doc, q.quote)
            if page is not None:
                q.page = page
                verified_quotes.append(q)
        if verified_quotes:
            d.quotes = verified_quotes
            ok.append(d)
        else:
            dropped.append(d)
    return ok, dropped

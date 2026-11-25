"""Верификатор цитат: защита от галлюцинаций.
Каждая цитата дефекта должна дословно (с точностью до пробелов/регистра) присутствовать в документе.
Иначе дефект отбрасывается. Заодно проставляет номер страницы."""
from __future__ import annotations

import re

from .schema import Defect, Document


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
    """Возвращает (подтверждённые, отброшенные)."""
    ok, dropped = [], []
    for d in defects:
        page = find_page(doc, d.quote)
        if page is None:
            dropped.append(d)
        else:
            d.page = page
            ok.append(d)
    return ok, dropped

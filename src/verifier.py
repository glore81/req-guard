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
    """Находит страницу (с 1) для PDF-документа."""
    q = _norm(quote)
    if not q:
        return None
    for i, page in enumerate(doc.pages, start=1):
        if q in _norm(page):
            return i
    return None


def find_line(doc: Document, quote: str) -> int | None:
    """Находит номер строки (с 1) для MD/TXT-документа."""
    q = _norm(quote)
    if not q:
        return None
    lines = doc.text.split("\n")
    # Ищем строку, содержащую цитату
    for i, line in enumerate(lines, start=1):
        if q in _norm(line):
            return i
    # Цитата может занимать несколько строк — ищем в скользящем окне
    full_norm = _norm(doc.text)
    if q in full_norm:
        # Находим позицию и считаем строки до неё
        pos = full_norm.index(q)
        original_prefix = doc.text[:pos + len(quote)]
        return original_prefix.count("\n") + 1
    return None


def verify(doc: Document, defects: list[Defect]) -> tuple[list[Defect], list[Defect]]:
    """Возвращает (подтверждённые, отброшенные).
    Дефект подтверждён, если хотя бы одна цитата найдена в документе.
    Ненайденные цитаты удаляются из списка.
    Для PDF заполняет page, для MD/TXT заполняет line."""
    ok, dropped = [], []
    for d in defects:
        verified_quotes: list[Quote] = []
        for q in d.quotes:
            if doc.is_pdf:
                page = find_page(doc, q.quote)
                if page is not None:
                    q.page = page
                    q.line = None
                    verified_quotes.append(q)
            else:
                line = find_line(doc, q.quote)
                if line is not None:
                    q.line = line
                    q.page = None
                    verified_quotes.append(q)
        if verified_quotes:
            d.quotes = verified_quotes
            ok.append(d)
        else:
            dropped.append(d)
    return ok, dropped

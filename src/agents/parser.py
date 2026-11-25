"""Агент 1 (человек 2): выделяет отдельные требования из документа.
Вход: Document. Выход: list[Requirement].
Если llm=None — возвращает заглушку (для разработки остальных частей)."""
from __future__ import annotations

from ..schema import Document, Requirement

PROMPT = """Ты — аналитик требований. Из документа ниже выдели ВСЕ отдельные требования.
Для каждого верни JSON-объект: {{"doc_id": "<ID из документа или null>", "text": "<краткая формулировка>", "quote": "<ДОСЛОВНАЯ цитата из документа>"}}.
Цитата должна быть скопирована без изменений. Верни JSON-массив.

ДОКУМЕНТ:
{document}
"""


def run(doc: Document, llm=None) -> list[Requirement]:
    if llm is None:
        return _stub(doc)
    # TODO (человек 2): длинные документы разбивать на части
    items = llm.call_json(PROMPT.format(document=doc.text))
    return [
        Requirement(id=f"R-{i:03d}", text=it["text"], quote=it["quote"], doc_id=it.get("doc_id"))
        for i, it in enumerate(items, start=1)
    ]


def _stub(doc: Document) -> list[Requirement]:
    lines = [l.strip() for l in doc.text.splitlines() if l.strip() and not l.startswith("#")]
    return [Requirement(id=f"R-{i:03d}", text=l[:80], quote=l) for i, l in enumerate(lines[:5], start=1)]

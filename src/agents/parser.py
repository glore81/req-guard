"""Агент-парсер: выделяет ВСЕ проверяемые требования из документа.
Вход: Document. Выход: list[Requirement].
Если llm=None — возвращает заглушку (для разработки остальных частей).

Участник 1: полная реализация.
"""
from __future__ import annotations

import re

from ..schema import Document, Requirement

# ---------- промпт для LLM ----------

PROMPT = """\
Ты — опытный системный аналитик. Твоя задача — извлечь из документа ВСЕ отдельные \
проверяемые требования, включая:
- Функциональные требования (Ф-1, Ф-2 и т.д.)
- Нефункциональные требования (производительность, доступность, безопасность)
- Требования к данным (поля, форматы, ограничения)
- Требования к интеграции / API (эндпоинты, параметры, статусы, логика)
- Критерии приёмки (каждая строка таблицы — отдельное требование)
- Бизнес-правила и ограничения из любого раздела

Правила:
1. Каждое требование — это ОДНО атомарное утверждение. Если один пункт содержит \
   несколько независимых правил, разбей на несколько требований.
2. `doc_id` — ID или нумерация из самого документа (например "Ф-1", "Ф-2", "НФ-1"). \
   Если явного ID нет, поставь null.
3. `text` — краткая формулировка (1-2 предложения своими словами), суть требования.
4. `quote` — ДОСЛОВНАЯ цитата из документа, подтверждающая это требование. \
   Копируй текст точно как есть, не изменяя ни одного символа. \
   Цитата должна быть достаточно длинной (от 10 символов), чтобы быть уникальной в документе, \
   но не длиннее 2-3 предложений.
5. `section` — название раздела документа, в котором найдено требование.

Верни JSON-массив объектов:
[
  {{
    "doc_id": "Ф-1" или null,
    "text": "краткая формулировка",
    "quote": "дословная цитата из документа",
    "section": "название раздела"
  }},
  ...
]

Извлеки ВСЕ требования, не пропускай ни одного. Лучше извлечь больше, чем пропустить.

ДОКУМЕНТ:
{document}
"""

# Если документ очень длинный, разбиваем на части
CHUNK_SIZE = 12000  # символов, с запасом для контекста модели


def run(doc: Document, llm=None) -> list[Requirement]:
    if llm is None:
        return _stub(doc)

    # Для коротких документов — один вызов
    if len(doc.text) <= CHUNK_SIZE:
        items = _call_llm(llm, doc.text)
    else:
        # Разбиваем по страницам и группируем чанки
        items = []
        chunks = _split_into_chunks(doc)
        for chunk in chunks:
            items.extend(_call_llm(llm, chunk))

    # Присваиваем сквозные ID и убираем дубли
    seen_quotes = set()
    result = []
    idx = 1
    for it in items:
        quote = it.get("quote", "")
        # Дедупликация по цитате
        norm_q = re.sub(r"\s+", " ", quote).strip().lower()
        if norm_q in seen_quotes:
            continue
        seen_quotes.add(norm_q)

        result.append(Requirement(
            id=f"R-{idx:03d}",
            text=it.get("text", ""),
            quote=quote,
            doc_id=it.get("doc_id"),
        ))
        idx += 1

    return result


def _call_llm(llm, text: str) -> list[dict]:
    """Один вызов LLM для извлечения требований из текста."""
    raw = llm.call_json(PROMPT.format(document=text))
    if isinstance(raw, dict):
        # Иногда модель оборачивает массив в объект
        for key in ("requirements", "items", "results", "data"):
            if key in raw and isinstance(raw[key], list):
                return raw[key]
        return []
    if isinstance(raw, list):
        return raw
    return []


def _split_into_chunks(doc: Document) -> list[str]:
    """Разбивает документ на чанки по страницам, не превышая CHUNK_SIZE."""
    chunks = []
    current = ""
    for page in doc.pages:
        if len(current) + len(page) > CHUNK_SIZE and current:
            chunks.append(current)
            current = ""
        current += page + "\n"
    if current.strip():
        chunks.append(current)
    return chunks


# ---------- заглушка для --dry-run ----------

def _stub(doc: Document) -> list[Requirement]:
    """Парсер без LLM: паттерн-матчинг для типичных ТЗ.
    Находит: Ф-*, НФ-*, пронумерованные пункты, строки с ключевыми словами,
    строки таблиц с параметрами API, критерии приёмки.
    Для MD/TXT заполняет line (с 1), для PDF — page."""
    reqs = []
    idx = 1
    seen = set()

    def _add(text: str, quote: str, doc_id=None, line_num=None):
        nonlocal idx
        norm = re.sub(r"\s+", " ", quote).strip().lower()
        if norm in seen or len(norm) < 15:
            return
        seen.add(norm)
        reqs.append(Requirement(
            id=f"R-{idx:03d}", text=text[:200], quote=quote, doc_id=doc_id,
            page=None if not doc.is_pdf else None,
            line=line_num if not doc.is_pdf else None,
        ))
        idx += 1

    lines = doc.text.splitlines()
    for i, raw in enumerate(lines):
        line = raw.strip()
        if not line:
            continue

        ln = i + 1  # строки с 1

        # 1. Пункты вида "* **Ф-1.** ..." или "Ф-1. ..."
        m = re.match(r"^\*?\s*\*?\*?(Ф-\d+)\.\*?\*?\s*(.+)", line)
        if m:
            _add(m.group(2), m.group(2), doc_id=m.group(1), line_num=ln)
            continue

        # 2. Нумерованные пункты в логике API: "1. Проверить..."
        m2 = re.match(r"^(\d+)\.\s+(.{15,})", line)
        if m2:
            _add(m2.group(2), m2.group(2), line_num=ln)
            continue

        # 3. HTTP-статусы: "**200.** Ответ..."
        m3 = re.match(r"^\*?\*?(\d{3})\.\*?\*?\s*(.+)", line)
        if m3:
            _add(f"HTTP {m3.group(1)}: {m3.group(2)}", line, line_num=ln)
            continue

        # 4. Строки с ключевыми словами требований
        lower = line.lower()
        keywords = ["должн", "необходим", "обязан", "запрещ", "не допуск",
                     "в течение", "не более", "не менее", "включительно",
                     "максимум", "минимум", "от 1", "до 1",
                     "при достижении", "при ошибке", "при изменении",
                     "не используются", "не используется"]
        if any(kw in lower for kw in keywords) and len(line) > 20:
            _add(line, line, line_num=ln)
            continue

        # 5. Строки таблиц с параметрами (| param | format | ...)
        if line.startswith("|") and "---" not in line:
            cells = [c.strip() for c in line.split("|") if c.strip()]
            if len(cells) >= 3 and cells[0].startswith("`"):
                param_name = cells[0].strip("`")
                desc = cells[-2] if len(cells) > 2 else ""
                _add(f"Параметр {param_name}: {desc}", line, line_num=ln)

    # Если совсем ничего — берём первые строки
    if not reqs:
        for j, l in enumerate(lines):
            l = l.strip()
            if l and not l.startswith("#") and len(l) > 15:
                _add(l[:120], l, line_num=j + 1)
                if idx > 10:
                    break

    return reqs

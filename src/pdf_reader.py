"""Чтение документа с сохранением номеров страниц. Поддерживает .pdf, .md, .txt.
Участник 1: полная реализация."""
from __future__ import annotations

import re
from pathlib import Path

from .schema import Document


def read_document(path: str) -> Document:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Файл не найден: {path}")
    suffix = p.suffix.lower()
    if suffix == ".pdf":
        pages = _read_pdf(p)
    elif suffix in (".md", ".txt"):
        pages = [p.read_text(encoding="utf-8")]
    else:
        raise ValueError(f"Неподдерживаемый формат: {suffix} (нужен .pdf, .md или .txt)")

    # Нормализуем текст каждой страницы: убираем лишние переносы внутри слов
    pages = [_clean_page(pg) for pg in pages]
    text = "\n".join(pages)
    return Document(name=p.name, text=text, pages=pages)


def _read_pdf(p: Path) -> list[str]:
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise RuntimeError("Установите зависимости: pip install -r requirements.txt") from e
    reader = PdfReader(str(p))
    return [(page.extract_text() or "") for page in reader.pages]


def _clean_page(text: str) -> str:
    """Убирает типичные артефакты PDF-извлечения:
    - склеивает слова разорванные переносом (тре-\\nбования → требования)
    - нормализует множественные пробелы
    """
    # Склейка переносов: "тре-\nбования" -> "требования"
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    # Склейка разрывов строк внутри абзаца (не после пустой строки и не перед маркером)
    text = re.sub(r"(?<!\n)\n(?!\n)(?!\s*[-*#|>Ф\d])", " ", text)
    # Множественные пробелы
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()

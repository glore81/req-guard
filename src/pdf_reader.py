"""Чтение документа с сохранением номеров страниц. Поддерживает .pdf, .md, .txt."""
from __future__ import annotations

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
    return Document(name=p.name, text="\n".join(pages), pages=pages)


def _read_pdf(p: Path) -> list[str]:
    try:
        from pypdf import PdfReader
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("Установите зависимости: pip install -r requirements.txt") from e
    reader = PdfReader(str(p))
    return [(page.extract_text() or "") for page in reader.pages]

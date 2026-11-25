"""Общая схема данных. Все трое участников опираются на неё — менять только по договорённости.

Формат JSON на выходе pipeline:
  meta:         {document, date, model, agent_version}
  requirements: [{id, doc_id|null, page|null, line?, text, quote}]
  defects:      [{defect_id, req_id, related_req_ids, defect_type,
                  quotes: [{req_id, page|null, line?, quote}],
                  explanation, question}]

Серьёзность НЕ хранится в JSON — выводится из defect_type в report.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# Типы дефектов (критерии ISO/IEC/IEEE 29148:2018 п. 5.2.5-5.2.6, IEEE 830 п. 4.3)
DEFECT_TYPES = {
    "ambiguity": "Неоднозначность",
    "unverifiable": "Непроверяемость",
    "contradiction": "Противоречие",
    "incomplete": "Неполнота",
    "design_decision": "Лишнее проектное решение",
    "gap": "Пропуск",
    "duplicate": "Дубль",
    "other": "Прочее",
}

# Серьёзность определяется типом дефекта (не хранится отдельно)
SEVERITY_BY_TYPE = {
    "unverifiable": "critical",
    "contradiction": "critical",
    "incomplete": "critical",
    "gap": "critical",
    "ambiguity": "major",
    "design_decision": "minor",
    "duplicate": "minor",
    "other": "major",
}
SEVERITY_RU = {
    "critical": "критичный",
    "major": "существенный",
    "minor": "незначительный",
}


@dataclass
class Requirement:
    id: str                       # Сквозной ID агента: R-001, R-002...
    text: str                     # Краткая формулировка (для таблицы соответствия)
    quote: str                    # Дословная цитата из документа
    doc_id: Optional[str] = None  # ID из самого документа (Ф-1, НФ-1...)
    page: Optional[int] = None    # Страница (PDF), null для MD/TXT
    line: Optional[int] = None    # Номер строки (с 1), null для PDF


@dataclass
class Quote:
    """Одна цитата-доказательство дефекта."""
    req_id: str                   # К какому требованию относится
    page: Optional[int] = None    # Страница (заполняет верификатор)
    line: Optional[int] = None    # Номер строки (с 1)
    quote: str = ""               # Дословная цитата


@dataclass
class Defect:
    id: str                       # Сквозной ID дефекта: D-001, D-002...
    req_id: str                   # ID требования или "SET" для дефекта набора
    defect_type: str              # Ключ из DEFECT_TYPES
    quotes: list[Quote] = field(default_factory=list)   # Цитаты-доказательства
    explanation: str = ""         # Почему это дефект
    question: str = ""            # Уточняющий вопрос автору ТЗ
    related_req_ids: list[str] = field(default_factory=list)

    @property
    def severity(self) -> str:
        return SEVERITY_BY_TYPE.get(self.defect_type, "major")

    @property
    def is_critical(self) -> bool:
        return self.severity == "critical"


@dataclass
class Document:
    name: str
    text: str                     # Полный текст
    pages: list[str]              # Текст по страницам
    is_pdf: bool = True           # True = page-based, False = line-based (MD/TXT)


@dataclass
class RunPassport:
    document_name: str
    date: str
    model: str
    agent_version: str


@dataclass
class Result:
    passport: RunPassport
    requirements: list[Requirement]
    req_defects: list[Defect]     # Дефекты отдельных требований
    set_defects: list[Defect]     # Дефекты набора в целом
    dropped: list[Defect] = field(default_factory=list)

    def to_json(self) -> dict:
        """Сериализация в формат sample.json."""
        return {
            "meta": {
                "document": self.passport.document_name,
                "date": self.passport.date,
                "model": self.passport.model,
                "agent_version": self.passport.agent_version,
            },
            "requirements": [
                {k: v for k, v in [
                    ("id", r.id), ("doc_id", r.doc_id), ("page", r.page),
                    ("line", r.line), ("text", r.text), ("quote", r.quote),
                ] if v is not None or k in ("id", "text", "quote")}
                for r in self.requirements
            ],
            "defects": [
                {
                    "defect_id": d.id, "req_id": d.req_id,
                    "related_req_ids": d.related_req_ids,
                    "defect_type": d.defect_type,
                    "quotes": [
                        {k: v for k, v in [
                            ("req_id", q.req_id), ("page", q.page),
                            ("line", q.line), ("quote", q.quote),
                        ] if v is not None or k in ("req_id", "quote")}
                        for q in d.quotes
                    ],
                    "explanation": d.explanation,
                    "question": d.question,
                }
                for d in self.req_defects + self.set_defects
            ],
        }

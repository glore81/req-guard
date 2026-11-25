"""Общая схема данных. Все трое участников опираются на неё — менять только по договорённости."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional

# Типы дефектов (критерии ISO/IEC/IEEE 29148:2018 п. 5.2.5-5.2.6, IEEE 830 п. 4.3)
DEFECT_TYPES = {
    "ambiguity": "Неоднозначность",
    "unverifiable": "Непроверяемость",
    "contradiction": "Противоречие",
    "incomplete": "Неполнота / пропуск",
    "design_decision": "Лишнее проектное решение",
    "duplicate": "Дублирование",
    "other": "Прочее",
}
SEVERITIES = ("critical", "major", "minor")
# Критичные по ТЗ: непроверяемость, противоречие, неполнота
CRITICAL_TYPES = {"unverifiable", "contradiction", "incomplete"}


@dataclass
class Requirement:
    id: str                      # ID агента: R-001, R-002...
    text: str                    # краткая формулировка
    quote: str                   # дословная цитата из документа
    doc_id: Optional[str] = None  # ID из самого документа, если есть
    page: Optional[int] = None


@dataclass
class Defect:
    req_id: str                  # ID требования или "SET" для проверки набора
    defect_type: str             # ключ из DEFECT_TYPES
    severity: str                # critical | major | minor
    quote: str                   # дословная цитата-доказательство (обязательна!)
    explanation: str             # почему это нарушение
    question: str = ""           # уточняющий вопрос автору ТЗ
    page: Optional[int] = None   # заполняет верификатор
    related_req_ids: list[str] = field(default_factory=list)  # для противоречий


@dataclass
class Document:
    name: str
    text: str                    # полный текст
    pages: list[str]             # текст по страницам (для ссылок на место)


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
    req_defects: list[Defect]    # дефекты отдельных требований
    set_defects: list[Defect]    # дефекты набора в целом
    dropped: list[Defect] = field(default_factory=list)  # отброшены верификатором (цитата не найдена)

    def to_dict(self) -> dict:
        return asdict(self)

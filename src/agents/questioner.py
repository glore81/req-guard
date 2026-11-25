"""Агент 4 (человек 2): уточняющие вопросы (25% оценки!).
Дозаполняет поле question у дефектов, где его нет, и убирает дубли вопросов.
TODO: сгруппировать вопросы по темам, расставить приоритеты."""
from __future__ import annotations

from ..schema import Defect


def run(defects: list[Defect], llm=None) -> list[Defect]:
    # TODO (человек 2): через LLM сформулировать вопросы для дефектов без question
    for d in defects:
        if not d.question:
            d.question = "Уточните, пожалуйста, формулировку этого требования."
    return defects

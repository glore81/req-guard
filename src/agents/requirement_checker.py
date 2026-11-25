"""Агент 2 (человек 2): проверяет КАЖДОЕ требование по критериям качества.
Критерии: ISO/IEC/IEEE 29148:2018 п. 5.2.5, 5.2.6; IEEE 830-1998 п. 4.3
(однозначность, проверяемость, полнота, непротиворечивость, отсутствие проектных решений...).
Вход: Requirement. Выход: list[Defect]."""
from __future__ import annotations

from ..schema import Defect, Requirement

PROMPT = """Ты — эксперт по качеству требований (ISO 29148, IEEE 830).
Проверь требование на: неоднозначность (абстрактные слова), непроверяемость, неполноту,
лишние проектные решения. Не придирайся, если требование нормальное — верни [].
Для каждого нарушения верни: {{"defect_type": "ambiguity|unverifiable|incomplete|design_decision|other",
"severity": "critical|major|minor", "quote": "<ДОСЛОВНАЯ цитата>", "explanation": "<почему>",
"question": "<уточняющий вопрос автору ТЗ>"}}. Ответ на русском. Верни JSON-массив.

ТРЕБОВАНИЕ {rid}: {quote}
"""


def run(req: Requirement, llm=None) -> list[Defect]:
    if llm is None:
        return _stub(req)
    items = llm.call_json(PROMPT.format(rid=req.id, quote=req.quote))
    return [Defect(req_id=req.id, **{k: it.get(k, "") for k in
            ("defect_type", "severity", "quote", "explanation", "question")}) for it in items]


def _stub(req: Requirement) -> list[Defect]:
    return [Defect(req.id, "ambiguity", "major", req.quote,
                   "[ЗАГЛУШКА] Пример найденного нарушения.", "[ЗАГЛУШКА] Что имелось в виду?")]

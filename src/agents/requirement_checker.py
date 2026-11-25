"""Агент 2: проверяет КАЖДОЕ требование по критериям качества.
Критерии: ISO/IEC/IEEE 29148:2018 п. 5.2.5, 5.2.6; IEEE 830-1998 п. 4.3
Вход: Requirement, номер дефекта. Выход: list[Defect]."""
from __future__ import annotations

from ..schema import Defect, Quote, Requirement

PROMPT = """Ты — эксперт по качеству требований (ISO 29148, IEEE 830).
Проверь требование на: неоднозначность (абстрактные слова), непроверяемость, неполноту,
лишние проектные решения. Не придирайся, если требование нормальное — верни [].
Для каждого нарушения верни:
{{"defect_type": "ambiguity|unverifiable|incomplete|design_decision|gap|other",
"quote": "<ДОСЛОВНАЯ цитата-доказательство из текста требования>",
"explanation": "<почему это дефект>",
"question": "<уточняющий вопрос автору ТЗ>"}}
Цитата должна быть скопирована без изменений. Ответ на русском. Верни JSON-массив.

ТРЕБОВАНИЕ {rid}: {quote}
"""


def run(req: Requirement, llm=None, defect_counter: list | None = None) -> list[Defect]:
    if defect_counter is None:
        defect_counter = [0]  # мутабельный счётчик для сквозной нумерации
    if llm is None:
        return _stub(req, defect_counter)
    items = llm.call_json(PROMPT.format(rid=req.id, quote=req.quote))
    if not isinstance(items, list):
        items = []
    result = []
    for it in items:
        defect_counter[0] += 1
        result.append(Defect(
            id=f"D-{defect_counter[0]:03d}",
            req_id=req.id,
            defect_type=it.get("defect_type", "other"),
            quotes=[Quote(req_id=req.id, quote=it.get("quote", ""))],
            explanation=it.get("explanation", ""),
            question=it.get("question", ""),
        ))
    return result


def _stub(req: Requirement, defect_counter: list) -> list[Defect]:
    defect_counter[0] += 1
    return [Defect(
        id=f"D-{defect_counter[0]:03d}",
        req_id=req.id,
        defect_type="ambiguity",
        quotes=[Quote(req_id=req.id, quote=req.quote)],
        explanation="[ЗАГЛУШКА] Пример найденного нарушения.",
        question="[ЗАГЛУШКА] Что имелось в виду?",
    )]

"""Агент 3 (человек 2): проверяет НАБОР требований целиком — противоречия, пропуски, дубли.
Вход: list[Requirement]. Выход: list[Defect] (req_id="SET")."""
from __future__ import annotations

from ..schema import Defect, Requirement

PROMPT = """Ты — эксперт по качеству требований. Ниже полный набор требований.
Найди: противоречия между требованиями, пропущенные области (чего не хватает для начала разработки),
дубли. Для каждого верни: {{"defect_type": "contradiction|incomplete|duplicate|other",
"severity": "critical|major|minor", "quote": "<ДОСЛОВНАЯ цитата-доказательство>",
"related_req_ids": ["R-001", ...], "explanation": "<почему>", "question": "<вопрос автору ТЗ>"}}.
Ответ на русском. Верни JSON-массив.

ТРЕБОВАНИЯ:
{reqs}
"""


def run(reqs: list[Requirement], llm=None) -> list[Defect]:
    if llm is None:
        return []
    listing = "\n".join(f"{r.id}: {r.quote}" for r in reqs)
    items = llm.call_json(PROMPT.format(reqs=listing))
    return [Defect(req_id="SET", defect_type=it.get("defect_type", "other"),
                   severity=it.get("severity", "major"), quote=it.get("quote", ""),
                   explanation=it.get("explanation", ""), question=it.get("question", ""),
                   related_req_ids=it.get("related_req_ids", [])) for it in items]

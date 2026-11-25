"""Агент 3: проверяет НАБОР требований целиком — противоречия, пропуски, дубли.
Вход: list[Requirement], номер дефекта. Выход: list[Defect] (req_id="SET")."""
from __future__ import annotations

from ..schema import Defect, Quote, Requirement

PROMPT = """Ты — эксперт по качеству требований. Ниже полный набор требований.
Найди: противоречия между требованиями, пропущенные области, дубли.
Для каждого нарушения верни:
{{"defect_type": "contradiction|incomplete|duplicate|gap|other",
"related_req_ids": ["R-001", "R-003"],
"quotes": [{{"req_id": "R-001", "quote": "<ДОСЛОВНАЯ цитата>"}}, {{"req_id": "R-003", "quote": "<ДОСЛОВНАЯ цитата>"}}],
"explanation": "<почему это дефект>",
"question": "<уточняющий вопрос автору ТЗ>"}}
Каждая цитата должна быть скопирована без изменений. Ответ на русском. Верни JSON-массив.

ТРЕБОВАНИЯ:
{reqs}
"""


def run(reqs: list[Requirement], llm=None, defect_counter: list | None = None) -> list[Defect]:
    if defect_counter is None:
        defect_counter = [0]
    if llm is None:
        return []
    listing = "\n".join(f"{r.id} ({r.doc_id or 'нет ID'}): {r.quote}" for r in reqs)
    items = llm.call_json(PROMPT.format(reqs=listing))
    if not isinstance(items, list):
        items = []
    result = []
    for it in items:
        defect_counter[0] += 1
        # Собираем quotes
        raw_quotes = it.get("quotes", [])
        quotes = []
        for rq in raw_quotes:
            if isinstance(rq, dict):
                quotes.append(Quote(req_id=rq.get("req_id", "SET"), quote=rq.get("quote", "")))
        result.append(Defect(
            id=f"D-{defect_counter[0]:03d}",
            req_id="SET",
            defect_type=it.get("defect_type", "other"),
            quotes=quotes,
            explanation=it.get("explanation", ""),
            question=it.get("question", ""),
            related_req_ids=it.get("related_req_ids", []),
        ))
    return result

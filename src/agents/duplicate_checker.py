"""Агент поиска дублей среди найденных дефектов.

Разные агенты ищут независимо, поэтому одна и та же проблема может
попасть в отчёт несколько раз (например, «нет метода чтения настроек»
находили и requirement_checker, и оба прохода set_checker).

Работает БЕЗ модели — обычным кодом: не тратит лимит API и ничего
не может выдумать. Два дефекта считаются дублями, если одновременно:
  1. их цитаты пересекаются (одна содержит другую) или содержат
     одно и то же словосочетание — PHRASE_WORDS значимых слов подряд
     (одна проблема, процитированная в разных местах: «подсказка
     о минимально допустимой сумме» и «меньше минимально допустимой»);
  2. объяснения похожи по словам (общих значимых слов ≥ SIMILARITY,
     а для совпадения только по словосочетанию — ≥ PHRASE_SIMILARITY).
Порог подобран на реальных отчётах: у настоящих дублей сходство
0.19–0.47, у разных дефектов на той же строке — 0.03–0.11.

Из группы дублей остаётся один дефект — с наибольшим числом цитат
(при равенстве — дефект набора). К нему добавляются недостающие
цитаты и связанные требования остальных. После склейки дефекты
перенумеровываются (D-001, D-002, ...) без пропусков."""

from __future__ import annotations

import re

from ..schema import Defect

SIMILARITY = 0.15
PHRASE_WORDS = 2
PHRASE_SIMILARITY = 0.2

_STOP = set(
    "и в во не на что как для по из к с со а но или ли же это при от до "
    "о об его её их она он они быть есть который которая которые также только".split()
)


def run(
        req_defects: list[Defect],
        set_defects: list[Defect],
) -> tuple[list[Defect], list[Defect], int]:
    """Возвращает (дефекты требований, дефекты набора, сколько дублей склеено)."""

    defects = req_defects + set_defects
    n = len(defects)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    words = [_stems(d.explanation) for d in defects]

    phrases = [_phrases(d) for d in defects]

    for i in range(n):
        for j in range(i + 1, n):
            sim = _jaccard(words[i], words[j])
            if (_quotes_overlap(defects[i], defects[j]) and sim >= SIMILARITY) or \
                    (phrases[i] & phrases[j] and sim >= PHRASE_SIMILARITY):
                parent[find(i)] = find(j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)

    keep: set[int] = set()
    for members in groups.values():
        best = max(members, key=lambda k: (len(defects[k].quotes),
                                           defects[k].req_id == "SET",
                                           -k))
        _absorb(defects[best], [defects[k] for k in members if k != best])
        keep.add(best)

    kept = [defects[i] for i in range(n) if i in keep]
    merged = n - len(kept)

    for num, d in enumerate(kept, start=1):
        d.id = f"D-{num:03d}"

    return (
        [d for d in kept if d.req_id != "SET"],
        [d for d in kept if d.req_id == "SET"],
        merged,
    )


def _norm(text: str) -> str:
    return re.sub(r"[\s|`*.]+", " ", text).strip().lower()


def _quotes_overlap(a: Defect, b: Defect) -> bool:
    for qa in a.quotes:
        for qb in b.quotes:
            x, y = _norm(qa.quote), _norm(qb.quote)
            if x and y and (x in y or y in x):
                return True
    return False


def _phrases(d: Defect) -> set[tuple[str, ...]]:
    """Словосочетания из PHRASE_WORDS значимых слов подряд во всех цитатах."""
    out = set()
    for q in d.quotes:
        seq = [w[:5] for w in re.findall(r"[а-яёa-z0-9]+", q.quote.lower())
               if len(w) > 3 and w not in _STOP]
        for k in range(len(seq) - PHRASE_WORDS + 1):
            out.add(tuple(seq[k:k + PHRASE_WORDS]))
    return out


def _stems(text: str) -> set[str]:
    """Значимые слова, обрезанные до 5 букв (грубая замена стемминга)."""
    return {
        w[:5]
        for w in re.findall(r"[а-яёa-z0-9]+", text.lower())
        if len(w) > 3 and w not in _STOP
    }


def _jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def _absorb(target: Defect, others: list[Defect]) -> None:
    """Добавляет к оставшемуся дефекту цитаты и связи склеенных."""
    seen = [_norm(q.quote) for q in target.quotes]
    related = set(target.related_req_ids) - {"—"}

    for d in others:
        for q in d.quotes:
            n = _norm(q.quote)
            # Цитату, которая уже содержится в имеющейся (или наоборот), не добавляем.
            if not any(n in s or s in n for s in seen):
                target.quotes.append(q)
                seen.append(n)
        if d.req_id != "SET":
            related.add(d.req_id)
        related.update(r for r in d.related_req_ids if r != "—")

    related.discard(target.req_id)
    if related:
        target.related_req_ids = sorted(related)
    if not target.question:
        target.question = next((d.question for d in others if d.question), "")
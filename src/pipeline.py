"""Оркестратор: парсер → проверка требований → проверка набора → вопросы → верификатор.
Участник 1: полная реализация (склейка всей цепочки).
"""
from __future__ import annotations

import datetime
import subprocess
import sys

from .agents import parser, questioner, requirement_checker, set_checker
from .schema import Document, Result, RunPassport
from .verifier import verify


def agent_version() -> str:
    try:
        return subprocess.check_output(
            ["git", "describe", "--tags", "--always", "--dirty"],
            stderr=subprocess.DEVNULL, text=True,
        ).strip()
    except Exception:
        return "unversioned"


def run_pipeline(doc: Document, llm=None, model_name: str = "stub") -> Result:
    """Запускает полный конвейер анализа требований."""

    _log("Парсинг требований...")
    reqs = parser.run(doc, llm)
    _log(f"  Найдено требований: {len(reqs)}")

    # Проверка каждого требования отдельно
    _log("Проверка отдельных требований...")
    req_defects = []
    # Батчим, чтобы не упереться в rate limit бесплатного тарифа
    for i, r in enumerate(reqs, 1):
        defects = requirement_checker.run(r, llm)
        req_defects.extend(defects)
        if i % 5 == 0:
            _log(f"  Проверено {i}/{len(reqs)}")
    _log(f"  Найдено дефектов отдельных требований: {len(req_defects)}")

    # Проверка набора требований (противоречия, дубли)
    _log("Проверка набора требований...")
    set_defects = set_checker.run(reqs, llm)
    _log(f"  Найдено дефектов набора: {len(set_defects)}")

    # Генерация уточняющих вопросов
    _log("Генерация уточняющих вопросов...")
    req_defects = questioner.run(req_defects, llm)
    set_defects = questioner.run(set_defects, llm)

    # Верификация цитат (анти-галлюцинация)
    _log("Верификация цитат...")
    req_defects, dropped1 = verify(doc, req_defects)
    set_defects, dropped2 = verify(doc, set_defects)
    total_dropped = dropped1 + dropped2
    if total_dropped:
        _log(f"  ⚠ Отброшено дефектов (цитата не найдена): {len(total_dropped)}")
    _log(f"  Итого подтверждённых: {len(req_defects)} + {len(set_defects)}")

    passport = RunPassport(
        document_name=doc.name,
        date=datetime.date.today().isoformat(),
        model=model_name,
        agent_version=agent_version(),
    )
    return Result(passport, reqs, req_defects, set_defects, total_dropped)


def _log(msg: str):
    print(msg, file=sys.stderr)

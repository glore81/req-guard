"""Оркестратор (человек 1): парсер -> проверка требований -> проверка набора -> вопросы -> верификатор."""
from __future__ import annotations

import datetime
import subprocess

from .agents import parser, questioner, requirement_checker, set_checker
from .schema import Result, RunPassport
from .verifier import verify


def agent_version() -> str:
    try:
        return subprocess.check_output(["git", "describe", "--tags", "--always", "--dirty"],
                                       stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return "unversioned"


def run_pipeline(doc, llm=None, model_name: str = "stub") -> Result:
    reqs = parser.run(doc, llm)
    req_defects = [d for r in reqs for d in requirement_checker.run(r, llm)]
    set_defects = set_checker.run(reqs, llm)

    req_defects = questioner.run(req_defects, llm)
    set_defects = questioner.run(set_defects, llm)

    # Верификатор: отбрасываем всё, чьей цитаты нет в документе
    req_defects, dropped1 = verify(doc, req_defects)
    set_defects, dropped2 = verify(doc, set_defects)

    passport = RunPassport(document_name=doc.name,
                           date=datetime.date.today().isoformat(),
                           model=model_name, agent_version=agent_version())
    return Result(passport, reqs, req_defects, set_defects, dropped1 + dropped2)

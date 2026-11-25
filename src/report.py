"""Генератор отчёта: Result (или dict из JSON) → report.md на русском.

Может работать двумя способами:
1. Из pipeline: build_report_from_result(Result) → str
2. Из JSON-файла: build_report(dict) → str  или  python report.py result.json report.md

Формат JSON — см. schema.py / sample.json.
Серьёзность в JSON не передаётся: выводится из defect_type.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime

DEFECT_TYPES = {
    "ambiguity": "Неоднозначность",
    "unverifiable": "Непроверяемость",
    "incomplete": "Неполнота",
    "design_decision": "Лишнее проектное решение",
    "contradiction": "Противоречие",
    "gap": "Пропуск",
    "duplicate": "Дубль",
    "other": "Прочее",
}
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
SEVERITY_RU = {"critical": "критичный", "major": "существенный", "minor": "незначительный"}


def git_version():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return "не определена"


def esc(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def dtype(d):
    return DEFECT_TYPES.get(d.get("defect_type"), d.get("defect_type", "?"))


def severity(d):
    return SEVERITY_BY_TYPE.get(d.get("defect_type"), "major")


def is_critical(d):
    return severity(d) == "critical"


def is_set(d):
    return d.get("req_id") == "SET"


def affected(d):
    if is_set(d):
        return d.get("related_req_ids", [])
    return [d["req_id"]] + d.get("related_req_ids", [])


def loc(o):
    """Место в документе: страница и/или строка; page может быть null (Markdown)."""
    parts = []
    if o.get("page") is not None:
        parts.append(f"стр. {o['page']}")
    if o.get("line") is not None:
        parts.append(f"строка {o['line']}")
    return ", ".join(parts) or "место не указано"


def quote_lines(d):
    return [f"  - Цитата ({q['req_id']}, {loc(q)}): «{q['quote']}»"
            for q in d.get("quotes", [])]


def build_report(data: dict) -> str:
    """Генерация отчёта из JSON-словаря (формат sample.json)."""
    meta = data.get("meta", {})
    reqs = data.get("requirements", [])
    defects = data.get("defects", [])
    req_defects = [d for d in defects if not is_set(d)]
    set_defects = [d for d in defects if is_set(d)]

    by_req = {}
    for d in req_defects:
        by_req.setdefault(d["req_id"], []).append(d)

    L = ["# Отчёт о проверке требований", ""]

    # 1. Паспорт
    L += ["## 1. Паспорт прогона", "",
          f"- **Документ:** {meta.get('document', '—')}",
          f"- **Дата:** {meta.get('date') or datetime.now().strftime('%Y-%m-%d %H:%M')}",
          f"- **Модель:** {meta.get('model', '—')}",
          f"- **Версия агента:** {meta.get('agent_version') or git_version()}", ""]

    # 2. Таблица требований
    L += ["## 2. Выделенные требования", "",
          "| ID в отчёте | ID в документе | Место | Краткая формулировка | Цитата |",
          "|---|---|---|---|---|"]
    for r in reqs:
        L.append(f"| {r['id']} | {esc(r.get('doc_id') or '(присвоен агентом)')} | "
                 f"{loc(r)} | {esc(r.get('text', ''))} | {esc(r['quote'])} |")
    L.append("")

    # 3. Проверка отдельных требований
    L += ["## 3. Проверка отдельных требований", ""]
    for r in reqs:
        ds = by_req.get(r["id"], [])
        L += [f"### {r['id']} ({r.get('doc_id') or 'без номера'})", "", f"> {r['quote']}", ""]
        if not ds:
            L += ["Нарушений не найдено.", ""]
            continue
        for d in ds:
            L.append(f"- **{d['defect_id']}: {dtype(d)}** ({SEVERITY_RU[severity(d)]})")
            L += quote_lines(d)
            L.append(f"  - Почему это дефект: {d['explanation']}")
        L.append("")

    # 4. Проверка набора
    L += ["## 4. Проверка набора требований", ""]
    if not set_defects:
        L += ["Нарушений на уровне набора не найдено.", ""]
    for d in set_defects:
        L.append(f"- **{d['defect_id']}: {dtype(d)}** ({SEVERITY_RU[severity(d)]}), "
                 f"затронуты: {', '.join(affected(d))}")
        L += quote_lines(d)
        L.append(f"  - Почему это дефект: {d['explanation']}")
    L.append("")

    # 5. Уточняющие вопросы
    L += ["## 5. Уточняющие вопросы автору документа", "",
          "| № | Дефект | Требования | Тип | Вопрос |", "|---|---|---|---|---|"]
    for i, d in enumerate(defects, 1):
        L.append(f"| {i} | {d['defect_id']} | {', '.join(affected(d))} | {dtype(d)} | {esc(d.get('question', ''))} |")
    L.append("")

    # 6. Сводка
    crit = [d for d in defects if is_critical(d)]
    L += ["## 6. Сводка", "",
          f"- Требований выделено: **{len(reqs)}**",
          f"- Требований с нарушениями: **{len(by_req)}**",
          f"- Нарушений всего: **{len(defects)}** (на уровне набора: {len(set_defects)})",
          f"- Критичных дефектов: **{len(crit)}**", ""]
    if crit:
        L += ["Критичные дефекты:", ""]
        for d in crit:
            q = "; ".join(f"«{x['quote']}» ({x['req_id']}, {loc(x)})"
                          for x in d.get("quotes", []))
            L.append(f"- {d['defect_id']} — {dtype(d)}: {q}")
        L.append("")

    # 7. Итог
    L += ["## 7. Итог", ""]
    if crit:
        L += [f"**Начинать разработку и тестирование по этому документу нельзя** — "
              f"найдено критичных дефектов: {len(crit)}.", "",
              "Исправить в первую очередь:", ""]
        for i, d in enumerate(crit, 1):
            L.append(f"{i}. {d['defect_id']} ({', '.join(affected(d))}) — {dtype(d)}: {d['explanation']}")
    else:
        L.append("Критичных дефектов нет, разработку начинать можно; "
                 "незначительные замечания желательно закрыть параллельно.")
    L.append("")
    return "\n".join(L)


def build_report_from_result(result) -> str:
    """Обёртка: принимает Result (dataclass), конвертирует в dict и строит отчёт."""
    return build_report(result.to_json())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("input_json")
    ap.add_argument("output_md")
    a = ap.parse_args()
    with open(a.input_json, encoding="utf-8") as f:
        data = json.load(f)
    with open(a.output_md, "w", encoding="utf-8") as f:
        f.write(build_report(data))
    print(f"Отчёт записан: {a.output_md}")

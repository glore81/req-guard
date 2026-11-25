"""Генератор отчёта на русском (человек 3). Структура — по ТЗ организаторов:
паспорт, таблица ID, проверка каждого требования, проверка набора, итоги, вывод."""
from __future__ import annotations

from .schema import CRITICAL_TYPES, DEFECT_TYPES, Defect, Result


def _label(t: str) -> str:
    return DEFECT_TYPES.get(t, t)


def _is_critical(d: Defect) -> bool:
    return d.severity == "critical" or d.defect_type in CRITICAL_TYPES


def build_report(r: Result) -> str:
    all_defects = r.req_defects + r.set_defects
    critical = [d for d in all_defects if _is_critical(d)]
    out: list[str] = []

    p = r.passport
    out += ["# Отчёт о проверке требований", "", "## 1. Паспорт запуска", "",
            f"- Документ: {p.document_name}", f"- Дата: {p.date}",
            f"- Модель: {p.model}", f"- Версия агента: {p.agent_version}", ""]

    out += ["## 2. Соответствие ID", "", "| ID агента | ID в документе | Формулировка |", "|---|---|---|"]
    for q in r.requirements:
        out.append(f"| {q.id} | {q.doc_id or '— (присвоен агентом)'} | {q.text} |")
    out.append("")

    out += ["## 3. Проверка каждого требования", ""]
    for q in r.requirements:
        ds = [d for d in r.req_defects if d.req_id == q.id]
        out.append(f"### {q.id}: {q.text}")
        out.append(f"> {q.quote}")
        if not ds:
            out.append("\nНарушений не найдено.\n")
            continue
        for d in ds:
            out += ["", f"- **{_label(d.defect_type)}** ({d.severity}), стр. {d.page}",
                    f"  - Цитата: «{d.quote}»", f"  - Почему: {d.explanation}",
                    f"  - Вопрос автору: {d.question}"]
        out.append("")

    out += ["## 4. Проверка набора требований в целом", ""]
    if not r.set_defects:
        out.append("Нарушений на уровне набора не найдено.\n")
    for d in r.set_defects:
        rel = f" (связаны: {', '.join(d.related_req_ids)})" if d.related_req_ids else ""
        out += [f"- **{_label(d.defect_type)}** ({d.severity}), стр. {d.page}{rel}",
                f"  - Цитата: «{d.quote}»", f"  - Почему: {d.explanation}",
                f"  - Вопрос автору: {d.question}"]
    out.append("")

    out += ["## 5. Итоги", "",
            f"- Требований: {len(r.requirements)}",
            f"- Нарушений: {len(all_defects)}",
            f"- Критичных дефектов: {len(critical)}", ""]
    for d in critical:
        out.append(f"  - [{d.req_id}] {_label(d.defect_type)}: «{d.quote}»")
    out.append("")

    out += ["## 6. Уточняющие вопросы к автору ТЗ", ""]
    qs = [d for d in all_defects if d.question]
    for i, d in enumerate(qs, start=1):
        out.append(f"{i}. [{d.req_id}] {d.question}")
    out.append("")

    ready = not critical
    out += ["## 7. Заключение", "",
            ("Разработку и тестирование **можно начинать**." if ready else
             "Разработку и тестирование **начинать рано**: сначала нужно устранить критичные дефекты."),
            "", "Что исправить в первую очередь:" if critical else ""]
    for d in critical[:5]:
        out.append(f"- [{d.req_id}] {d.explanation}")
    if r.dropped:
        out += ["", f"_Служебно: верификатор отбросил {len(r.dropped)} находок без подтверждённой цитаты._"]
    return "\n".join(out) + "\n"

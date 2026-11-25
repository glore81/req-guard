"""Запуск: python main.py <файл требований> <файл отчёта> [--dry-run] [--no-cache]

Сохраняет:
  - <report>.md  — Markdown-отчёт
  - <report>.json — промежуточный JSON (формат sample.json)

Кэш ответов LLM лежит в .llm_cache/ (см. src/llm.py). Для финального прогона
на сдачу используйте --no-cache или удалите папку .llm_cache/ вручную —
так отчёт гарантированно получен от текущей версии агента, а не из кэша
старого прогона.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

from src.pdf_reader import read_document
from src.pipeline import run_pipeline
from src.report import build_report_from_result

CACHE_DIR = Path(".llm_cache")


def main() -> int:
    ap = argparse.ArgumentParser(description="AI-агент проверки качества требований (ТЗ)")
    ap.add_argument("requirements", help="путь к документу требований (.pdf, .md, .txt)")
    ap.add_argument("report", help="путь к файлу отчёта (.md)")
    ap.add_argument("--dry-run", action="store_true", help="без LLM, на заглушках (для разработки)")
    ap.add_argument("--no-cache", action="store_true",
                     help="не использовать и не писать кэш ответов LLM (для финального прогона)")
    ap.add_argument("--clear-cache", action="store_true",
                     help="удалить .llm_cache/ перед запуском (требования и report всё равно обязательны)")
    args = ap.parse_args()

    if args.clear_cache and CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)
        print(f"Кэш очищен: {CACHE_DIR}")

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    doc = read_document(args.requirements)
    llm, model = None, "stub (dry-run)"
    if not args.dry_run:
        from src.llm import LLM
        llm = LLM(use_cache=not args.no_cache)
        model = llm.model

    result = run_pipeline(doc, llm, model)

    # Сохраняем отчёт (.md)
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(build_report_from_result(result), encoding="utf-8")

    # Сохраняем промежуточный JSON (.json рядом с .md)
    json_path = report_path.with_suffix(".json")
    json_path.write_text(json.dumps(result.to_json(), ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Готово: {report_path}  +  {json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

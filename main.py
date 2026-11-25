"""Запуск: python main.py <файл требований> <файл отчёта> [--dry-run]

Сохраняет:
  - <report>.md  — Markdown-отчёт
  - <report>.json — промежуточный JSON (формат sample.json)
"""
import argparse
import json
import sys
from pathlib import Path

from src.pdf_reader import read_document
from src.pipeline import run_pipeline
from src.report import build_report_from_result


def main() -> int:
    ap = argparse.ArgumentParser(description="AI-агент проверки качества требований (ТЗ)")
    ap.add_argument("requirements", help="путь к документу требований (.pdf, .md, .txt)")
    ap.add_argument("report", help="путь к файлу отчёта (.md)")
    ap.add_argument("--dry-run", action="store_true", help="без LLM, на заглушках (для разработки)")
    args = ap.parse_args()

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    doc = read_document(args.requirements)
    llm, model = None, "stub (dry-run)"
    if not args.dry_run:
        from src.llm import LLM
        llm = LLM()
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

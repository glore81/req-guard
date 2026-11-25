"""Запуск: python main.py <файл требований> <файл отчёта> [--dry-run]"""
import argparse
import os
import sys
from pathlib import Path

from src.pdf_reader import read_document
from src.pipeline import run_pipeline
from src.report import build_report


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
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(build_report(result), encoding="utf-8")
    print(f"Готово: {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

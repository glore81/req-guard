# ReqGuard — AI-агент проверки качества требований

Агент статически проверяет готовый документ требований (ТЗ): разбирает каждое требование,
оценивает его и весь набор по критериям ISO/IEC/IEEE 29148:2018 (п. 5.2.5, 5.2.6) и IEEE 830-1998 (п. 4.3),
формулирует уточняющие вопросы к автору и пишет отчёт на русском.

## Установка

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Получение LLM-ключа

1. Откройте https://aistudio.google.com/apikey и создайте бесплатный ключ Gemini API.
2. Скопируйте `.env.example` в `.env` и впишите ключ: `GEMINI_API_KEY=...`

## Запуск

```bash
python main.py docs/requirements.pdf reports/report.md
```

Режим без LLM (заглушки, для разработки): добавьте `--dry-run`.

Отчёт сохраняется по пути, указанному вторым аргументом.

## Архитектура

```
PDF -> pdf_reader -> parser -> requirement_checker (на каждое требование)
                            -> set_checker (на весь набор)
                            -> questioner -> verifier (проверка цитат) -> report
```

- `src/schema.py` — общая схема данных
- `src/agents/` — агенты на базе LLM
- `src/verifier.py` — отбрасывает находки, цитаты которых нет в документе
- `src/report.py` — генератор отчёта

TODO: описать подробнее после реализации агентов.

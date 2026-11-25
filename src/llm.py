"""Единая обёртка над LLM (по умолчанию Gemini через Google AI Studio, бесплатный тариф).
Все агенты вызывают только call_json().

Кэш на диске (.llm_cache/): каждый ответ сохраняется по хэшу запроса.
Если прогон упал на лимите/перегрузке посередине — после перезапуска уже
полученные ответы берутся с диска, модель вызывается только для оставшихся.
Отключить кэш: LLM(use_cache=False) / флаг --no-cache.

Устойчивость к ошибкам бесплатного тарифа Gemini — различаем три случая:
  * 429 "лимит в минуту" — ждём столько, сколько просит Google (обычно 10-60 с),
    и повторяем ТУ ЖЕ модель (она рабочая, просто нужно переждать минуту);
  * 429 "лимит на день" — модель выбывает до конца прогона (до сброса лимита
    ещё часы), сразу идём к следующей модели, не тратя на неё время;
  * 503 "сервер перегружен" — модель на минуту в конец очереди, сразу пробуем
    следующую; если других живых моделей нет — ждём 30 с и повторяем.
Порядок моделей: LLM_MODEL, затем LLM_FALLBACKS из .env (через запятую)."""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path

CACHE_DIR = Path(".llm_cache")

OVERLOAD_BENCH_SEC = 60      # на сколько убрать модель после 503
LONG_LIMIT_SEC = 120         # если Google просит ждать дольше — считаем лимит дневным
MAX_MINUTE_WAIT_SEC = 60     # максимум ожидания при лимите в минуту

DEFAULT_FALLBACKS = [
    "gemini-3.5-flash-lite",
    "gemini-2.5-flash-lite",
]


class LLM:
    def __init__(self, model: str | None = None, api_key: str | None = None,
                 use_cache: bool = True, fallbacks: list[str] | None = None):
        primary = model or os.getenv("LLM_MODEL", "gemini-3.6-flash")
        if fallbacks is None:
            env_fb = os.getenv("LLM_FALLBACKS")
            fallbacks = [m.strip() for m in env_fb.split(",") if m.strip()] if env_fb else DEFAULT_FALLBACKS
        # Модели по порядку: сначала основная, потом резервные (без дублей).
        self.models = [primary] + [m for m in fallbacks if m != primary]
        self.model = primary  # для обратной совместимости (report.py читает .model)
        self.use_cache = use_cache
        self._bench: dict[str, float] = {}  # модель -> время, до которого её не трогаем
        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("Не задан GEMINI_API_KEY. Скопируйте .env.example в .env и впишите ключ.")
        from google import genai
        from google.genai import types
        self._client = genai.Client(
            api_key=key,
            http_options=types.HttpOptions(api_version="v1beta"),
        )

    def call_json(self, prompt: str, retries: int = 4):
        """Вызывает модель и возвращает распарсенный JSON (см. описание модуля)."""
        # Готовый ответ любой модели из цепочки — берём с диска.
        if self.use_cache:
            for model in self.models:
                cache_file = self._cache_file(model, prompt)
                if cache_file.exists():
                    self.model = model
                    return json.loads(cache_file.read_text(encoding="utf-8"))

        last_err = None
        for attempt in range(retries * len(self.models)):
            model = self._pick_model()
            if model is None:
                break  # у всех моделей кончился дневной лимит
            try:
                resp = self._client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config={"response_mime_type": "application/json", "temperature": 0.2},
                )
                result = _parse_json(resp.text)
                if self.use_cache:
                    cache_file = self._cache_file(model, prompt)
                    cache_file.parent.mkdir(parents=True, exist_ok=True)
                    cache_file.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
                self.model = model  # запоминаем, какая модель реально ответила
                return result
            except Exception as e:  # лимиты, перегрузка сервера, сеть, невалидный JSON
                last_err = e
                wait = _retry_delay(e)

                if _is_daily_limit(e) or (wait is not None and wait > LONG_LIMIT_SEC):
                    self._bench[model] = time.time() + (wait or 3600)
                    print(f"[llm] {model}: дневной лимит исчерпан, больше её не пробую")
                    continue

                if _is_rate_limit(e):
                    d = min((wait or 20) + 1, MAX_MINUTE_WAIT_SEC)
                    print(f"[llm] {model}: лимит запросов в минуту, жду {d:.0f} с")
                    time.sleep(d)
                    continue

                if _is_overloaded(e):
                    if self._has_other_live(model):
                        self._bench[model] = time.time() + OVERLOAD_BENCH_SEC
                        print(f"[llm] {model}: сервер перегружен (503), пробую другую модель")
                    else:
                        print(f"[llm] {model}: сервер перегружен (503), жду 30 с")
                        time.sleep(30)
                    continue

                # Сеть, битый JSON и прочее — короткая пауза и повтор.
                time.sleep(min(2 ** (attempt % 4), 8))

        raise RuntimeError(
            f"LLM не ответила ни на одной из моделей {self.models}. "
            f"Если ниже 'per day' — кончился дневной лимит проекта, нужен ключ другого проекта. "
            f"Последняя ошибка: {last_err}"
        )

    def _pick_model(self) -> str | None:
        """Первая модель по порядку, которая сейчас не на паузе.
        Если все на короткой паузе (503) — дожидаемся ближайшей.
        Если у всех дневной лимит — None."""
        now = time.time()
        live = [m for m in self.models if self._bench.get(m, 0) <= now]
        if live:
            return live[0]
        soonest = min(self.models, key=lambda m: self._bench[m])
        wait = self._bench[soonest] - now
        if wait > LONG_LIMIT_SEC:
            return None
        time.sleep(wait)
        return soonest

    def _has_other_live(self, model: str) -> bool:
        now = time.time()
        return any(m != model and self._bench.get(m, 0) <= now for m in self.models)

    def _cache_file(self, model: str, prompt: str) -> Path:
        key = hashlib.sha256(f"{model}::{prompt}".encode("utf-8")).hexdigest()
        return CACHE_DIR / f"{key}.json"


def _retry_delay(e: Exception) -> float | None:
    """Сколько секунд Google просит подождать (поле retryDelay в ошибке 429)."""
    m = re.search(r"retryDelay'?\"?:\s*'?\"?(\d+(?:\.\d+)?)s", str(e))
    if m:
        return float(m.group(1))
    m = re.search(r"retry in (\d+(?:\.\d+)?)s", str(e))
    return float(m.group(1)) if m else None


def _is_daily_limit(e: Exception) -> bool:
    text = str(e).lower()
    return "per day" in text or "perday" in text


def _is_rate_limit(e: Exception) -> bool:
    """Ошибка превышения лимита запросов (HTTP 429)."""
    code = getattr(e, "code", None) or getattr(e, "status_code", None)
    if code == 429:
        return True
    text = str(e).lower()
    return "429" in text or "resource_exhausted" in text or "rate limit" in text or "quota" in text


def _is_overloaded(e: Exception) -> bool:
    """Перегрузка/недоступность сервера (HTTP 503, MODEL_CAPACITY_EXHAUSTED)."""
    code = getattr(e, "code", None) or getattr(e, "status_code", None)
    if code == 503:
        return True
    text = str(e).lower()
    return ("503" in text or "unavailable" in text or "overloaded" in text
            or "high demand" in text or "capacity_exhausted" in text
            or "no capacity available" in text)


def _parse_json(text: str):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    return json.loads(text)
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
Порядок моделей: LLM_MODEL, затем LLM_FALLBACKS из .env (через запятую).

Два провайдера:
  * Gemini (Google AI Studio) — модели без префикса: "gemini-2.5-flash-lite";
  * Groq (официальная библиотека groq) — модели с префиксом "groq:":
    "groq:openai/gpt-oss-120b". Нужен GROQ_API_KEY (console.groq.com).
Модели провайдера без ключа в .env пропускаются, поэтому достаточно
ключа хотя бы одного провайдера."""
from __future__ import annotations

import copy
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

GROQ_PREFIX = "groq:"
# Groq в JSON-режиме обязан вернуть объект, поэтому просим обёртку {"result": ...}
# и потом её снимаем — агенты получают тот же JSON, что и от Gemini.
GROQ_SYSTEM = (
    'Отвечай строго одним JSON-объектом вида {"result": <ответ>}, '
    "где <ответ> — JSON-значение (обычно массив), которое требует задание."
)

# По умолчанию — комбинация провайдеров. Достаточно вписать ключи в .env:
# модели провайдера без ключа пропускаются автоматически.
#   оба ключа     -> требования проверяет Gemini, противоречия ищет Groq,
#                    при сбое Gemini запросы подхватывает Groq;
#   только Gemini -> всё на Gemini;   только Groq -> всё на Groq.
# Переопределить можно в .env: LLM_MODEL, LLM_FALLBACKS, SET_CHECKER_MODEL.
DEFAULT_MODEL = "gemini-2.5-flash-lite"
DEFAULT_FALLBACKS = [
    "gemini-3.5-flash-lite",
    "gemini-3.6-flash",
    "groq:openai/gpt-oss-120b",
]
# Модель для поиска противоречий (set_checker): рассуждающая модель
# находит многошаговые противоречия заметно лучше облегчённых.
DEFAULT_SET_CHECKER_MODEL = "groq:openai/gpt-oss-120b"


class LLM:
    def __init__(self, model: str | None = None, api_key: str | None = None,
                 use_cache: bool = True, fallbacks: list[str] | None = None):
        primary = model or os.getenv("LLM_MODEL") or DEFAULT_MODEL
        if fallbacks is None:
            env_fb = os.getenv("LLM_FALLBACKS")
            fallbacks = [m.strip() for m in env_fb.split(",") if m.strip()] if env_fb else list(DEFAULT_FALLBACKS)
        # Модели по порядку: сначала основная, потом резервные (без дублей).
        self.models = [primary] + [m for m in fallbacks if m != primary]
        self.model = primary  # для обратной совместимости (report.py читает .model)
        self.use_cache = use_cache
        self._bench: dict[str, float] = {}  # модель -> время, до которого её не трогаем
        gemini_key = api_key or os.getenv("GEMINI_API_KEY")
        self._groq_key = os.getenv("GROQ_API_KEY")

        # Модели провайдера без ключа пропускаем (с предупреждением).
        usable = [
            m for m in self.models
            if (self._groq_key if _is_groq(m) else gemini_key)
        ]
        if usable:
            if not self._groq_key and any(_is_groq(m) for m in self.models):
                print("[llm] нет GROQ_API_KEY — работаю только на Gemini")
            if not gemini_key and any(not _is_groq(m) for m in self.models):
                print("[llm] нет GEMINI_API_KEY — работаю только на Groq")
        if not usable:
            raise RuntimeError(
                "Не задан ключ ни одного провайдера. Скопируйте .env.example в .env "
                "и впишите GEMINI_API_KEY и/или GROQ_API_KEY."
            )
        self.models = usable
        self.model = usable[0]

        self._client = None
        self._groq_client = None
        if gemini_key and any(not _is_groq(m) for m in usable):
            from google import genai
            from google.genai import types
            self._client = genai.Client(
                api_key=gemini_key,
                http_options=types.HttpOptions(api_version="v1beta"),
            )

    def call_json(self, prompt: str, retries: int = 4, temperature: float = 0.2):
        """Вызывает модель и возвращает распарсенный JSON (см. описание модуля).
        temperature=0 — максимально повторяемый ответ (нужно парсеру)."""
        # Готовый ответ любой модели из цепочки — берём с диска.
        if self.use_cache:
            for model in self.models:
                cache_file = self._cache_file(model, prompt, temperature)
                if cache_file.exists():
                    self.model = model
                    return json.loads(cache_file.read_text(encoding="utf-8"))

        last_err = None
        too_big: set[str] = set()   # модели, которым этот запрос не по размеру (413)
        for attempt in range(retries * len(self.models)):
            model = self._pick_model(exclude=too_big)
            if model is None:
                break  # у всех моделей кончился дневной лимит
            try:
                result = self._generate(model, prompt, temperature)
                if self.use_cache:
                    cache_file = self._cache_file(model, prompt, temperature)
                    cache_file.parent.mkdir(parents=True, exist_ok=True)
                    cache_file.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
                self.model = model  # запоминаем, какая модель реально ответила
                return result
            except Exception as e:  # лимиты, перегрузка сервера, сеть, невалидный JSON
                last_err = e
                wait = _retry_delay(e)

                if getattr(e, "code", None) == 413:
                    too_big.add(model)
                    print(f"[llm] {model}: запрос слишком большой для лимита модели, пробую другую")
                    continue

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

    def with_primary(self, model: str) -> "LLM":
        """Копия обёртки, где `model` идёт первой, а остальная цепочка — следом.
        Нужна, чтобы отдать отдельному агенту другую модель (SET_CHECKER_MODEL).
        Клиенты и учёт лимитов общие: если модель исчерпала дневной лимит,
        это знают все копии."""
        # Нет ключа нужного провайдера — остаёмся на основной цепочке
        # (о недостающем ключе уже сказано при создании LLM).
        if _is_groq(model) and not self._groq_key:
            return self
        if not _is_groq(model) and self._client is None:
            return self
        other = copy.copy(self)
        other.models = [model] + [m for m in self.models if m != model]
        other.model = model
        return other

    def _generate(self, model: str, prompt: str, temperature: float):
        """Один запрос к нужному провайдеру; возвращает распарсенный JSON."""
        if _is_groq(model):
            return self._groq(model[len(GROQ_PREFIX):], prompt, temperature)
        resp = self._client.models.generate_content(
            model=model,
            contents=prompt,
            config={"response_mime_type": "application/json", "temperature": temperature},
        )
        return _parse_json(resp.text)

    def _groq(self, model: str, prompt: str, temperature: float):
        """Запрос к Groq через официальную библиотеку groq."""
        from groq import APIStatusError, Groq  # ленивый импорт: нужен только при моделях groq:

        if self._groq_client is None:
            # max_retries=0: повторы и паузы делает наш call_json, а не библиотека.
            self._groq_client = Groq(api_key=self._groq_key, max_retries=0, timeout=180)

        try:
            resp = self._groq_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": GROQ_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
                response_format={"type": "json_object"},
            )
        except APIStatusError as e:
            response = getattr(e, "response", None)
            retry = response.headers.get("retry-after") if response is not None else None
            # Приводим к виду, который понимают _is_rate_limit/_retry_delay.
            raise ProviderError(
                e.status_code,
                f"{e.status_code} {e.message}" + (f" Please retry in {retry}s." if retry else ""),
            ) from None

        result = _parse_json(resp.choices[0].message.content)
        if isinstance(result, dict) and "result" in result:
            result = result["result"]
        return result

    def _pick_model(self, exclude: set[str] = frozenset()) -> str | None:
        """Первая модель по порядку, которая сейчас не на паузе.
        Если все на короткой паузе (503) — дожидаемся ближайшей.
        Если у всех дневной лимит (или запрос им не по размеру) — None."""
        now = time.time()
        candidates = [m for m in self.models if m not in exclude]
        if not candidates:
            return None
        live = [m for m in candidates if self._bench.get(m, 0) <= now]
        if live:
            return live[0]
        soonest = min(candidates, key=lambda m: self._bench[m])
        wait = self._bench[soonest] - now
        if wait > LONG_LIMIT_SEC:
            return None
        time.sleep(wait)
        return soonest

    def _has_other_live(self, model: str) -> bool:
        now = time.time()
        return any(m != model and self._bench.get(m, 0) <= now for m in self.models)

    def _cache_file(self, model: str, prompt: str, temperature: float = 0.2) -> Path:
        # Для температуры по умолчанию ключ прежний — старый кэш остаётся валидным.
        raw = f"{model}::{prompt}" if temperature == 0.2 else f"{model}::t={temperature}::{prompt}"
        key = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return CACHE_DIR / f"{key}.json"


class ProviderError(Exception):
    """Ошибка HTTP от провайдера (Groq); .code — HTTP-статус."""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


def _is_groq(model: str) -> bool:
    return model.startswith(GROQ_PREFIX)


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
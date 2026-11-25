"""Единая обёртка над LLM (по умолчанию Gemini через Google AI Studio, бесплатный тариф).
Все агенты вызывают только call_json().

Кэш на диске (.llm_cache/): каждый ответ сохраняется по хэшу запроса.
Если прогон упал на лимите посередине — после перезапуска уже полученные
ответы берутся с диска, модель вызывается только для оставшихся.
Побочный эффект: повторные прогоны становятся мгновенными и воспроизводимыми
(удобно для тестов и демо). Отключить кэш: LLM(use_cache=False)."""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path

CACHE_DIR = Path(".llm_cache")


class LLM:
    def __init__(self, model: str | None = None, api_key: str | None = None,
                 use_cache: bool = True):
        self.model = model or os.getenv("LLM_MODEL", "gemini-2.0-flash")
        self.use_cache = use_cache
        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("Не задан GEMINI_API_KEY. Скопируйте .env.example в .env и впишите ключ.")
        from google import genai  # ленивый импорт
        self._client = genai.Client(api_key=key)

    def call_json(self, prompt: str, retries: int = 4):
        """Вызывает модель и возвращает распарсенный JSON.
        Ретраи при сети/битом JSON — короткая пауза (1-2-4-8с).
        Ретраи при превышении лимита (429) — длинная пауза (30-45-60-60с),
        т.к. бесплатный тариф Gemini считается по минутам.
        Перед вызовом модели проверяет кэш на диске (по хэшу промпта + модели)."""
        cache_file = self._cache_file(prompt) if self.use_cache else None
        if cache_file is not None and cache_file.exists():
            return json.loads(cache_file.read_text(encoding="utf-8"))

        last_err = None
        for attempt in range(retries):
            try:
                resp = self._client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config={"response_mime_type": "application/json", "temperature": 0.2},
                )
                result = _parse_json(resp.text)
                if cache_file is not None:
                    cache_file.parent.mkdir(parents=True, exist_ok=True)
                    cache_file.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
                return result
            except Exception as e:  # лимиты бесплатного тарифа, сеть, невалидный JSON
                last_err = e
                if _is_rate_limit(e):
                    delay = min(30 + attempt * 15, 60)  # 30, 45, 60, 60 сек
                else:
                    delay = 2 ** attempt  # 1, 2, 4, 8 сек
                time.sleep(delay)
        raise RuntimeError(f"LLM не ответила после {retries} попыток: {last_err}")

    def _cache_file(self, prompt: str) -> Path:
        key = hashlib.sha256(f"{self.model}::{prompt}".encode("utf-8")).hexdigest()
        return CACHE_DIR / f"{key}.json"


def _is_rate_limit(e: Exception) -> bool:
    """Определяет, что ошибка вызвана превышением лимита запросов (HTTP 429)."""
    code = getattr(e, "code", None) or getattr(e, "status_code", None)
    if code == 429:
        return True
    text = str(e).lower()
    return "429" in text or "resource_exhausted" in text or "rate limit" in text or "quota" in text


def _parse_json(text: str):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    return json.loads(text)

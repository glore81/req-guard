"""Единая обёртка над LLM (по умолчанию Gemini через Google AI Studio, бесплатный тариф).
Все агенты вызывают только call_json()."""
from __future__ import annotations

import json
import os
import re
import time


class LLM:
    def __init__(self, model: str | None = None, api_key: str | None = None):
        self.model = model or os.getenv("LLM_MODEL", "gemini-2.0-flash")
        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("Не задан GEMINI_API_KEY. Скопируйте .env.example в .env и впишите ключ.")
        from google import genai  # ленивый импорт
        self._client = genai.Client(api_key=key)

    def call_json(self, prompt: str, retries: int = 4):
        """Вызывает модель и возвращает распарсенный JSON. Ретраи при лимитах и битом JSON."""
        last_err = None
        for attempt in range(retries):
            try:
                resp = self._client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config={"response_mime_type": "application/json", "temperature": 0.2},
                )
                return _parse_json(resp.text)
            except Exception as e:  # лимиты бесплатного тарифа, сеть, невалидный JSON
                last_err = e
                time.sleep(2 ** attempt)
        raise RuntimeError(f"LLM не ответила после {retries} попыток: {last_err}")


def _parse_json(text: str):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    return json.loads(text)

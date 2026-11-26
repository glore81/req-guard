"""Тесты обёртки LLM без сети: Gemini и Groq подменяются заглушками."""
import json
import sys
import types

import pytest


class _GeminiDaily(Exception):
    def __init__(self):
        super().__init__("429 RESOURCE_EXHAUSTED requests per day. 'retryDelay': '40000s'")
        self.code = 429


@pytest.fixture
def llm_module(monkeypatch):
    google = types.ModuleType("google")
    genai = types.ModuleType("google.genai")
    gtypes = types.ModuleType("google.genai.types")
    gtypes.HttpOptions = lambda **kw: None

    class Models:
        def generate_content(self, model, contents, config):
            raise _GeminiDaily()

    class Client:
        def __init__(self, **kw):
            self.models = Models()

    genai.Client = Client
    genai.types = gtypes
    google.genai = genai
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.genai", genai)
    monkeypatch.setitem(sys.modules, "google.genai.types", gtypes)

    from src import llm as module
    sleeps = []
    monkeypatch.setattr(module.time, "sleep", lambda s: sleeps.append(round(s)))
    module._sleeps = sleeps
    return module


def groq_server(monkeypatch, module, plan, sent):
    """Подменяет библиотеку groq: plan — ответы по очереди;
    кортеж (код, сообщение, retry-after) означает ошибку API."""
    groq = types.ModuleType("groq")

    class APIStatusError(Exception):
        def __init__(self, status_code, message, headers):
            super().__init__(message)
            self.status_code = status_code
            self.message = message
            self.response = types.SimpleNamespace(headers=headers)

    class Completions:
        def create(self, **kwargs):
            sent.append(kwargs)
            step = plan.pop(0)
            if isinstance(step, tuple):
                code, message, retry = step
                raise APIStatusError(code, message, {"retry-after": retry} if retry else {})
            message = types.SimpleNamespace(content=json.dumps(step))
            return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

    class Groq:
        def __init__(self, api_key, max_retries=2, timeout=None):
            assert api_key == "k" and max_retries == 0
            self.chat = types.SimpleNamespace(completions=Completions())

    groq.Groq = Groq
    groq.APIStatusError = APIStatusError
    monkeypatch.setitem(sys.modules, "groq", groq)


def test_gemini_daily_limit_falls_back_to_groq(llm_module, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    monkeypatch.setenv("GROQ_API_KEY", "k")
    sent = []
    groq_server(monkeypatch, llm_module, [{"result": [{"a": 1}]}], sent)

    llm = llm_module.LLM(model="gemini-2.5-flash-lite",
                         fallbacks=["groq:openai/gpt-oss-120b"], use_cache=False)

    assert llm.call_json("p") == [{"a": 1}]
    assert llm.model == "groq:openai/gpt-oss-120b"
    assert sent[0]["model"] == "openai/gpt-oss-120b"
    assert sent[0]["response_format"] == {"type": "json_object"}


def test_groq_minute_limit_waits_and_retries_same_model(llm_module, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    sent = []
    groq_server(monkeypatch, llm_module,
                [(429, "Rate limit on tokens per minute (TPM)", "7"), {"result": []}], sent)

    llm = llm_module.LLM(model="groq:openai/gpt-oss-120b", fallbacks=[], use_cache=False)

    assert llm.call_json("p") == []
    assert llm_module._sleeps == [8]


def test_groq_request_too_large_switches_model_without_waiting(llm_module, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    sent = []
    groq_server(monkeypatch, llm_module,
                [(413, "Request too large on tokens per minute (TPM)", None), {"result": [1]}], sent)

    llm = llm_module.LLM(model="groq:openai/gpt-oss-120b",
                         fallbacks=["groq:qwen/qwen3-32b"], use_cache=False)

    assert llm.call_json("p") == [1]
    assert [b["model"] for b in sent] == ["openai/gpt-oss-120b", "qwen/qwen3-32b"]
    assert llm_module._sleeps == []


def test_daily_limit_everywhere_fails_fast(llm_module, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    daily = (429, "Rate limit on requests per day (RPD)", "7380")
    groq_server(monkeypatch, llm_module, [daily], [])

    llm = llm_module.LLM(model="groq:openai/gpt-oss-120b", fallbacks=[], use_cache=False)

    with pytest.raises(RuntimeError):
        llm.call_json("p")
    assert llm_module._sleeps == []


def test_models_without_key_are_skipped(llm_module, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    llm = llm_module.LLM(model="gemini-2.5-flash-lite", fallbacks=["groq:openai/gpt-oss-120b"])

    assert llm.models == ["gemini-2.5-flash-lite"]


def test_no_keys_at_all(llm_module, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    with pytest.raises(RuntimeError):
        llm_module.LLM(model="gemini-2.5-flash-lite", fallbacks=[])


def test_with_primary_puts_model_first_and_shares_limits(llm_module, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    monkeypatch.setenv("GROQ_API_KEY", "k")
    llm = llm_module.LLM(model="gemini-2.5-flash-lite",
                         fallbacks=["gemini-3.5-flash-lite", "groq:openai/gpt-oss-120b"])

    set_llm = llm.with_primary("groq:openai/gpt-oss-120b")

    assert set_llm.models == ["groq:openai/gpt-oss-120b", "gemini-2.5-flash-lite", "gemini-3.5-flash-lite"]
    assert llm.models[0] == "gemini-2.5-flash-lite"          # основная цепочка не изменилась
    set_llm._bench["gemini-2.5-flash-lite"] = 1e18
    assert llm._bench["gemini-2.5-flash-lite"] == 1e18       # учёт лимитов общий


def test_with_primary_without_key_keeps_main_chain(llm_module, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    llm = llm_module.LLM(model="gemini-2.5-flash-lite", fallbacks=[])

    assert llm.with_primary("groq:openai/gpt-oss-120b") is llm


@pytest.mark.parametrize("gemini, groq, expected", [
    ("g", "k", "both"),
    ("g", None, "gemini"),
    (None, "k", "groq"),
])
def test_default_chain_follows_available_keys(llm_module, monkeypatch, gemini, groq, expected):
    for var in ("LLM_MODEL", "LLM_FALLBACKS"):
        monkeypatch.delenv(var, raising=False)
    for var, value in (("GEMINI_API_KEY", gemini), ("GROQ_API_KEY", groq)):
        if value:
            monkeypatch.setenv(var, value)
        else:
            monkeypatch.delenv(var, raising=False)

    llm = llm_module.LLM()
    providers = {"groq" if m.startswith("groq:") else "gemini" for m in llm.models}
    set_llm = llm.with_primary(llm_module.DEFAULT_SET_CHECKER_MODEL)

    if expected == "both":
        assert providers == {"gemini", "groq"}
        assert llm.models[0].startswith("gemini")
        assert set_llm.models[0] == "groq:openai/gpt-oss-120b"
    elif expected == "gemini":
        assert providers == {"gemini"}
        assert set_llm is llm
    else:
        assert providers == {"groq"}
        assert set_llm.models[0] == "groq:openai/gpt-oss-120b"
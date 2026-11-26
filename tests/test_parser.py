import pytest

from src.schema import Document
from src.agents import parser


class MockLLM:

    def __init__(self, response):
        self.response = response

    def call_json(self, prompt, **kwargs):
        return self.response


def test_extract_requirements():

    text = "Система должна быстро обрабатывать заявки."

    doc = Document(
        name="test.md",
        text=text,
        pages=[text],
        is_pdf=False
    )

    llm = MockLLM([
        {
            "doc_id": None,
            "text": "Обработка заявок",
            "quote": text
        }
    ])

    result = parser.run(doc, llm)

    assert len(result) == 1
    assert result[0].id == "R-001"
    assert result[0].quote == text
    assert result[0].line == 1


def test_invalid_quote():

    text = "Система должна отправлять уведомления."

    doc = Document(
        name="test.md",
        text=text,
        pages=[text],
        is_pdf=False
    )

    llm = MockLLM([
        {
            "doc_id": None,
            "text": "Удаление аккаунта",
            "quote": "Система должна удалять аккаунты."
        }
    ])

    with pytest.raises(ValueError):
        parser.run(doc, llm)


def test_empty_document():

    doc = Document(
        name="empty.md",
        text="",
        pages=[],
        is_pdf=False
    )

    with pytest.raises(ValueError):
        parser.run(doc, MockLLM([]))


def test_pdf_page_number():

    text = "Клиент может изменить лимит расходов."

    doc = Document(
        name="test.pdf",
        text=text,
        pages=[text],
        is_pdf=True
    )

    llm = MockLLM([
        {
            "doc_id": None,
            "text": "Изменение лимита",
            "quote": text
        }
    ])

    result = parser.run(doc, llm)

    assert result[0].page == 1
    assert result[0].line is None


def test_invalid_json_structure():

    text = "Система должна хранить настройки."

    doc = Document(
        name="test.md",
        text=text,
        pages=[text],
        is_pdf=False
    )

    llm = MockLLM({"unexpected": True})

    with pytest.raises(ValueError):
        parser.run(doc, llm)


def test_preserve_duplicate_requirements():

    quote = "Система должна отправлять уведомления."
    text = quote + "\n" + quote

    doc = Document(
        name="test.md",
        text=text,
        pages=[text],
        is_pdf=False
    )

    llm = MockLLM([
        {
            "doc_id": None,
            "text": "Отправка уведомлений",
            "quote": quote
        },
        {
            "doc_id": None,
            "text": "Отправка уведомлений",
            "quote": quote
        }
    ])

    result = parser.run(doc, llm)

    assert len(result) == 2
    assert result[0].id == "R-001"
    assert result[1].id == "R-002"
    assert result[0].line == 1
    assert result[1].line == 2


def test_drop_service_parts_removes_review_checklist_and_passport_rows():
    from src.agents.parser import _drop_service_parts
    from src.schema import Document, Requirement

    text = "\n".join([
        "### Функциональные требования",                       # 1
        "Клиент задаёт порог.",                                 # 2
        "### Ревью требований",                                 # 3
        "| Требование может быть протестировано | Да / Нет |",   # 4
        "### Общие параметры",                                  # 5
        "| **Author** | Школа тестирования |",                  # 6
        "| **REST type** | GET |",                              # 7
    ])
    doc = Document(name="t.md", text=text, pages=[text], is_pdf=False)
    reqs = [
        Requirement(id="R-001", text="t", quote="Клиент задаёт порог.", line=2),
        Requirement(id="R-002", text="t", quote="Требование может быть протестировано", line=4),
        Requirement(id="R-003", text="t", quote="Author | Школа тестирования", line=6),
        Requirement(id="R-004", text="t", quote="REST type | GET", line=7),
    ]

    kept = _drop_service_parts(reqs, doc)

    assert [r.line for r in kept] == [2, 7]
    assert [r.id for r in kept] == ["R-001", "R-002"]


def test_drop_service_parts_keeps_business_section_named_approval():
    from src.agents.parser import _drop_service_parts
    from src.schema import Document, Requirement

    text = "### Согласование заявки\nМенеджер согласует заявку в течение дня."
    doc = Document(name="t.md", text=text, pages=[text], is_pdf=False)
    reqs = [Requirement(id="R-001", text="t", quote="Менеджер согласует заявку в течение дня.", line=2)]

    assert _drop_service_parts(reqs, doc) == reqs
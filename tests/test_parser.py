
import pytest

from src.schema import Document
from src.agents import parser


class MockLLM:

    def __init__(self, response):
        self.response = response

    def call_json(self, prompt):
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

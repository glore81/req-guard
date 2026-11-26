import pytest

from src.schema import Requirement
from src.agents import requirement_checker


class MockLLM:

    def __init__(self, response):
        self.response = response

    def call_json(self, prompt, **kwargs):
        return self.response


def make_requirement():

    return Requirement(
        id="R-001",
        doc_id="Ф-1",
        text="Обработка заявок",
        quote="Система должна быстро обрабатывать заявки.",
        page=1
    )


def make_defect():

    return {
        "defect_type": "unverifiable",
        "quote": "быстро обрабатывать заявки",
        "explanation": "Отсутствует измеримый критерий скорости.",
        "question": "Какое максимальное время обработки заявки допустимо?"
    }


def test_detect_defect():

    req = make_requirement()
    llm = MockLLM([make_defect()])

    result = requirement_checker.run(req, llm)

    assert len(result) == 1
    assert result[0].id == "D-001"
    assert result[0].req_id == "R-001"
    assert result[0].defect_type == "unverifiable"
    assert result[0].severity == "critical"


def test_valid_requirement():

    req = Requirement(
        id="R-002",
        text="Время ответа",
        quote="Время ответа не более 2 секунд."
    )

    result = requirement_checker.run(
        req, MockLLM([])
    )

    assert result == []


def test_reject_hallucinated_quote():

    req = make_requirement()

    defect = make_defect()
    defect["quote"] = "Удаление банковского аккаунта"

    result = requirement_checker.run(
        req, MockLLM([defect])
    )

    assert result == []


def test_reject_invalid_defect_type():

    req = make_requirement()

    defect = make_defect()
    defect["defect_type"] = "unknown_type"

    result = requirement_checker.run(
        req, MockLLM([defect])
    )

    assert result == []


def test_remove_duplicate_defects():

    req = make_requirement()
    defect = make_defect()

    result = requirement_checker.run(
        req, MockLLM([defect, defect.copy()])
    )

    assert len(result) == 1


def test_preserve_defect_counter():

    req = make_requirement()
    counter = [5]

    result = requirement_checker.run(
        req, MockLLM([make_defect()]), counter
    )

    assert result[0].id == "D-006"
    assert counter[0] == 6


def test_preserve_quote_location():

    req = make_requirement()

    result = requirement_checker.run(
        req, MockLLM([make_defect()])
    )

    assert result[0].quotes[0].page == 1
    assert result[0].quotes[0].req_id == "R-001"


def test_invalid_json_structure():

    req = make_requirement()

    with pytest.raises(ValueError):
        requirement_checker.run(
            req, MockLLM({"unexpected": True})
        )
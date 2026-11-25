
import pytest

from src.schema import Requirement
from src.agents import set_checker


class MockLLM:

    def __init__(self, response):
        self.response = response

    def call_json(self, prompt):
        return self.response


def make_requirements():

    return [
        Requirement(
            id="R-001",
            text="Одно уведомление в месяц",
            quote="Система отправляет только одно уведомление в месяц.",
            page=1
        ),
        Requirement(
            id="R-002",
            text="Повторное уведомление",
            quote="Система отправляет повторное уведомление в том же месяце.",
            page=2
        )
    ]


def make_defect():

    return {
        "defect_type": "contradiction",
        "related_req_ids": ["R-001", "R-002"],
        "quotes": [
            {
                "req_id": "R-001",
                "quote": "только одно уведомление в месяц"
            },
            {
                "req_id": "R-002",
                "quote": "повторное уведомление в том же месяце"
            }
        ],
        "explanation": "Правила отправки уведомлений противоречат друг другу.",
        "question": "Допускается ли повторное уведомление в течение месяца?"
    }


def test_contradiction():

    result = set_checker.run(
        make_requirements(),
        MockLLM([make_defect()])
    )

    assert len(result) == 1
    assert result[0].req_id == "SET"
    assert result[0].defect_type == "contradiction"
    assert result[0].severity == "critical"
    assert len(result[0].quotes) == 2


def test_reject_unknown_requirement():

    defect = make_defect()
    defect["quotes"][1]["req_id"] = "R-999"

    result = set_checker.run(
        make_requirements(),
        MockLLM([defect])
    )

    assert result == []


def test_reject_invalid_quote():

    defect = make_defect()
    defect["quotes"][1]["quote"] = "Выдуманная цитата"

    result = set_checker.run(
        make_requirements(),
        MockLLM([defect])
    )

    assert result == []


def test_remove_duplicates():

    defect = make_defect()

    result = set_checker.run(
        make_requirements(),
        MockLLM([defect, defect.copy()])
    )

    assert len(result) == 1


def test_no_defects():

    result = set_checker.run(
        make_requirements(),
        MockLLM([])
    )

    assert result == []


def test_gap():

    defect = {
        "defect_type": "gap",
        "related_req_ids": ["R-001"],
        "quotes": [
            {
                "req_id": "R-001",
                "quote": "только одно уведомление в месяц"
            }
        ],
        "explanation": "Не определены условия отправки уведомления.",
        "question": "При каком событии отправляется уведомление?"
    }

    result = set_checker.run(
        make_requirements(),
        MockLLM([defect])
    )

    assert len(result) == 1
    assert result[0].defect_type == "gap"


def test_preserve_counter():

    counter = [10]

    result = set_checker.run(
        make_requirements(),
        MockLLM([make_defect()]),
        counter
    )

    assert result[0].id == "D-011"
    assert counter[0] == 11


def test_preserve_page_numbers():

    result = set_checker.run(
        make_requirements(),
        MockLLM([make_defect()])
    )

    assert result[0].quotes[0].page == 1
    assert result[0].quotes[1].page == 2


def test_empty_requirements():

    result = set_checker.run(
        [], MockLLM([])
    )

    assert result == []


def test_invalid_json_structure():

    with pytest.raises(ValueError):
        set_checker.run(
            make_requirements(),
            MockLLM({"unexpected": True})
        )

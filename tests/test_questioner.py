
import pytest

from src.schema import Defect, Quote
from src.agents import questioner


class MockLLM:

    def __init__(self, response):
        self.response = response
        self.calls = 0

    def call_json(self, prompt):
        self.calls += 1
        return self.response


def make_defect():

    return Defect(
        id="D-001",
        req_id="R-001",
        defect_type="unverifiable",
        quotes=[
            Quote(
                req_id="R-001",
                quote="Система должна работать быстро."
            )
        ],
        explanation="Не определён критерий скорости.",
        question=""
    )


def test_generate_question():

    defect = make_defect()

    llm = MockLLM([
        {
            "defect_id": "D-001",
            "question": "Какое максимальное время ответа допустимо?"
        }
    ])

    result = questioner.run([defect], llm)

    assert len(result) == 1
    assert result[0].question == (
        "Какое максимальное время ответа допустимо?"
    )


def test_preserve_defect_id():

    defect = make_defect()

    llm = MockLLM([
        {
            "defect_id": "D-001",
            "question": "Как измеряется скорость?"
        }
    ])

    result = questioner.run([defect], llm)

    assert result[0].id == "D-001"
    assert result[0].req_id == "R-001"
    assert result[0].defect_type == "unverifiable"


def test_reject_unknown_id():

    defect = make_defect()

    llm = MockLLM([
        {
            "defect_id": "D-999",
            "question": "Выдуманный вопрос?"
        }
    ])

    result = questioner.run([defect], llm)

    assert result[0].question != "Выдуманный вопрос?"
    assert result[0].question != ""


def test_fallback_question():

    defect = make_defect()

    result = questioner.run(
        [defect], MockLLM([])
    )

    assert result[0].question != ""
    assert result[0].question.endswith("?")


def test_preserve_existing_question():

    defect = make_defect()
    defect.question = "Какое время ответа допустимо?"

    result = questioner.run(
        [defect], MockLLM([])
    )

    assert result[0].question == (
        "Какое время ответа допустимо?"
    )


def test_add_question_mark():

    defect = make_defect()

    llm = MockLLM([
        {
            "defect_id": "D-001",
            "question": "Как измеряется скорость"
        }
    ])

    result = questioner.run([defect], llm)

    assert result[0].question.endswith("?")


def test_empty_defects():

    llm = MockLLM([])

    result = questioner.run([], llm)

    assert result == []
    assert llm.calls == 0


def test_dry_run():

    defect = make_defect()

    result = questioner.run([defect], None)

    assert result[0].question != ""


def test_invalid_json_structure():

    with pytest.raises(ValueError):

        questioner.run(
            [make_defect()],
            MockLLM({"unexpected": True})
        )


def test_batch_processing():

    defects = []

    for i in range(16):

        defect = make_defect()
        defect.id = f"D-{i + 1:03d}"
        defects.append(defect)

    llm = MockLLM([])

    result = questioner.run(defects, llm)

    assert len(result) == 16
    assert llm.calls == 2
    assert all(d.question for d in result)

import pytest
from types import SimpleNamespace

from src.agents.requirement_checker import run_batch


class MockLLM:

    def __init__(self, response=None):
        self.response = response if response is not None else []
        self.calls = 0
        self.prompts = []

    def call_json(self, prompt):
        self.calls += 1
        self.prompts.append(prompt)
        return self.response


def make_requirements(count):
    return [
        SimpleNamespace(
            id=f"R-{i:03d}",
            quote=f"Система должна быстро обработать заявку {i}.",
            page=1,
            line=i
        )
        for i in range(1, count + 1)
    ]


def make_defect(req):
    return {
        "req_id": req.id,
        "defect_type": "unverifiable",
        "quote": req.quote,
        "explanation": "Нет измеримого критерия скорости.",
        "question": "Какое время обработки допустимо?"
    }


def test_batch_reduces_api_calls():
    reqs = make_requirements(25)
    llm = MockLLM()

    run_batch(reqs, llm, batch_size=10)

    assert llm.calls == 3


def test_single_batch():
    reqs = make_requirements(10)
    llm = MockLLM()

    run_batch(reqs, llm, batch_size=10)

    assert llm.calls == 1


def test_detect_defects():
    reqs = make_requirements(3)
    llm = MockLLM([
        make_defect(reqs[0]),
        make_defect(reqs[1])
    ])

    result = run_batch(reqs, llm)

    assert len(result) == 2
    assert result[0].req_id == "R-001"
    assert result[1].req_id == "R-002"


def test_reject_unknown_requirement():
    reqs = make_requirements(2)

    defect = make_defect(reqs[0])
    defect["req_id"] = "R-999"

    result = run_batch(reqs, MockLLM([defect]))

    assert result == []


def test_reject_wrong_quote():
    reqs = make_requirements(2)

    defect = make_defect(reqs[0])
    defect["quote"] = reqs[1].quote

    result = run_batch(reqs, MockLLM([defect]))

    assert result == []


def test_remove_duplicate_defects():
    reqs = make_requirements(1)
    defect = make_defect(reqs[0])

    result = run_batch(
        reqs,
        MockLLM([defect, defect])
    )

    assert len(result) == 1


def test_preserve_counter():
    reqs = make_requirements(2)
    counter = [10]

    result = run_batch(
        reqs,
        MockLLM([
            make_defect(reqs[0]),
            make_defect(reqs[1])
        ]),
        counter
    )

    assert result[0].id == "D-011"
    assert result[1].id == "D-012"
    assert counter[0] == 12


def test_empty_requirements():
    llm = MockLLM()

    result = run_batch([], llm)

    assert result == []
    assert llm.calls == 0


def test_invalid_batch_size():
    with pytest.raises(ValueError):
        run_batch(
            make_requirements(3),
            MockLLM(),
            batch_size=0
        )


def test_dry_run():
    reqs = make_requirements(5)

    result = run_batch(reqs, llm=None)

    assert len(result) == 5


def test_invalid_json_structure():
    with pytest.raises(ValueError):
        run_batch(
            make_requirements(2),
            MockLLM({"invalid": True})
        )


def test_preserve_quote_location():
    reqs = make_requirements(2)

    result = run_batch(
        reqs,
        MockLLM([make_defect(reqs[1])])
    )

    assert result[0].quotes[0].page == 1
    assert result[0].quotes[0].line == 2
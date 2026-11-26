from src.schema import Defect, Quote
from src.agents import duplicate_checker


def make(did, req_id, dtype, quotes, explanation, related=None):
    return Defect(
        id=did,
        req_id=req_id,
        defect_type=dtype,
        quotes=[Quote(req_id=r, line=ln, quote=q) for r, ln, q in quotes],
        explanation=explanation,
        question="Вопрос?",
        related_req_ids=related or [],
    )


READ_METHOD = "Метод чтения настроек в спецификации API отсутствует, описан только метод сохранения."


def test_merge_same_problem_from_different_agents():
    req = [make("D-001", "R-014", "incomplete",
                [("R-014", 52, "читает и сохраняет настройки")], READ_METHOD)]
    st = [make("D-002", "SET", "gap",
               [("R-014", 52, "Приложение читает и сохраняет настройки"),
                ("R-019", 103, "Функциональные требования: чтение порога")],
               "В API отсутствует метод чтения настроек, описан только метод сохранения порога.",
               ["R-014", "R-019"])]

    req2, st2, merged = duplicate_checker.run(req, st)

    assert merged == 1
    assert req2 == []
    assert len(st2) == 1
    assert st2[0].id == "D-001"          # перенумерация без пропусков
    assert len(st2[0].quotes) == 2


def test_keep_different_problems_on_same_line():
    a = make("D-001", "R-020", "contradiction",
             [("R-020", 104, "REST type | GET")],
             "Метод сохраняет данные, а GET не должен менять состояние сервера.")
    b = make("D-002", "SET", "contradiction",
             [("R-020", 104, "REST type | GET"), ("R-034", 147, "Content-Type: application/json")],
             "Заголовок Content-Type задан для запроса без тела.",
             ["R-020", "R-034"])

    req2, st2, merged = duplicate_checker.run([a], [b])

    assert merged == 0
    assert len(req2) == 1 and len(st2) == 1


def test_no_merge_without_quote_overlap():
    a = make("D-001", "R-001", "ambiguity", [("R-001", 37, "активной карты")],
             "Термин не определён в документе.")
    b = make("D-002", "R-002", "ambiguity", [("R-002", 38, "проведённые покупки")],
             "Термин не определён в документе.")

    _, _, merged = duplicate_checker.run([a, b], [])

    assert merged == 0


def test_empty():
    assert duplicate_checker.run([], []) == ([], [], 0)
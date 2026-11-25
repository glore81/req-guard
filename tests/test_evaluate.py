import json
import pytest

from evaluation.evaluate import calculate_metrics, evaluate


def test_perfect_detection():
    result = calculate_metrics(10, 0, 0)

    assert result["precision"] == 1.0
    assert result["recall"] == 1.0
    assert result["f1_score"] == 1.0


def test_normal_detection():
    result = calculate_metrics(4, 1, 1)

    assert result["precision"] == 0.8
    assert result["recall"] == 0.8
    assert result["f1_score"] == 0.8


def test_false_positives():
    result = calculate_metrics(5, 5, 0)

    assert result["precision"] == 0.5
    assert result["recall"] == 1.0
    assert result["f1_score"] == 0.6667


def test_false_negatives():
    result = calculate_metrics(5, 0, 5)

    assert result["precision"] == 1.0
    assert result["recall"] == 0.5
    assert result["f1_score"] == 0.6667


def test_no_detected_defects():
    result = calculate_metrics(0, 0, 5)

    assert result["precision"] == 0
    assert result["recall"] == 0
    assert result["f1_score"] == 0


def test_all_predictions_wrong():
    result = calculate_metrics(0, 5, 3)

    assert result["f1_score"] == 0


def test_empty_data():
    result = calculate_metrics(0, 0, 0)

    assert result["precision"] == 0
    assert result["recall"] == 0
    assert result["f1_score"] == 0


def test_negative_tp():
    with pytest.raises(ValueError):
        calculate_metrics(-1, 0, 0)


def test_negative_fp():
    with pytest.raises(ValueError):
        calculate_metrics(0, -1, 0)


def test_negative_fn():
    with pytest.raises(ValueError):
        calculate_metrics(0, 0, -1)


def run_evaluation(tmp_path, monkeypatch, answers):

    monkeypatch.chdir(tmp_path)

    (tmp_path / "evaluation").mkdir()

    ground_truth = {
        "defects": [
            {
                "id": "GT-001",
                "status": "confirmed",
                "defect_type": "ambiguity",
                "explanation": "First defect"
            },
            {
                "id": "GT-002",
                "status": "confirmed",
                "defect_type": "incomplete",
                "explanation": "Second defect"
            },
            {
                "id": "GT-003",
                "status": "review",
                "defect_type": "gap",
                "explanation": "Unconfirmed defect"
            }
        ]
    }

    report = {
        "defects": [
            {
                "id": f"D-{i:03d}",
                "defect_type": "ambiguity",
                "explanation": "Detected defect",
                "quotes": []
            }
            for i in range(1, len(answers) + 1)
        ]
    }

    gt_path = tmp_path / "ground_truth.json"
    report_path = tmp_path / "report.json"

    gt_path.write_text(
        json.dumps(ground_truth),
        encoding="utf-8"
    )

    report_path.write_text(
        json.dumps(report),
        encoding="utf-8"
    )

    responses = iter(answers)

    monkeypatch.setattr(
        "builtins.input",
        lambda _: next(responses)
    )

    evaluate(gt_path, report_path)

    return json.loads(
        (tmp_path / "evaluation/metrics.json")
        .read_text(encoding="utf-8")
    )


def test_matching_defects(tmp_path, monkeypatch):

    result = run_evaluation(
        tmp_path,
        monkeypatch,
        ["GT-001", "GT-002"]
    )

    assert result["true_positives"] == 2
    assert result["false_negatives"] == 0
    assert result["f1_score"] == 1.0


def test_duplicate_matching(tmp_path, monkeypatch):

    result = run_evaluation(
        tmp_path,
        monkeypatch,
        ["GT-001", "GT-001"]
    )

    assert result["true_positives"] == 1
    assert result["false_positives"] == 1
    assert result["false_negatives"] == 1


def test_skip_defects(tmp_path, monkeypatch):

    result = run_evaluation(
        tmp_path,
        monkeypatch,
        ["GT-001", "SKIP"]
    )

    assert result["excluded"] == 1
    assert result["true_positives"] == 1
    assert result["false_positives"] == 0


def test_false_positive_mapping(tmp_path, monkeypatch):

    result = run_evaluation(
        tmp_path,
        monkeypatch,
        ["GT-001", "FP"]
    )

    assert result["true_positives"] == 1
    assert result["false_positives"] == 1
    assert result["false_negatives"] == 1


def test_missed_defects(tmp_path, monkeypatch):

    result = run_evaluation(
        tmp_path,
        monkeypatch,
        []
    )

    assert result["true_positives"] == 0
    assert result["false_negatives"] == 2
    assert result["missed_ids"] == [
        "GT-001",
        "GT-002"
    ]
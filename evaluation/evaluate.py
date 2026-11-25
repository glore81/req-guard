
"""Оценка качества обнаружения дефектов."""

import argparse
import json
from pathlib import Path


def calculate_metrics(tp, fp, fn):

    if min(tp, fp, fn) < 0:
        raise ValueError(
            "Количество дефектов не может быть отрицательным"
        )

    precision = tp / (tp + fp) if tp + fp else 0

    recall = tp / (tp + fn) if tp + fn else 0

    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0
    )

    return {
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4)
    }


def load_json(path):

    return json.loads(
        Path(path).read_text(encoding="utf-8-sig")
    )


def evaluate(ground_truth_path, report_path):

    ground_truth = load_json(ground_truth_path)
    report = load_json(report_path)

    confirmed = [
        d for d in ground_truth["defects"]
        if d["status"] == "confirmed"
    ]

    detected = report["defects"]

    matched = set()
    false_positives = 0
    excluded = 0

    print("\n=== ЭТАЛОННЫЕ ДЕФЕКТЫ ===\n")

    for defect in confirmed:

        print(
            defect["id"],
            defect["defect_type"]
        )

        print(defect["explanation"])
        print()

    valid_ids = {
        d["id"] for d in confirmed
    }

    print("\n=== ОЦЕНКА AI-ДЕФЕКТОВ ===")

    for defect in detected:

        print("\n" + "-" * 50)

        print(
            "ID:",
            defect.get(
                "defect_id",
                defect.get("id")
            )
        )

        print("Тип:", defect["defect_type"])
        print("Описание:", defect["explanation"])
        print("Вопрос:", defect.get("question", ""))

        for quote in defect.get("quotes", []):

            print(
                "Цитата:",
                quote.get("quote", "")
            )

        while True:

            answer = input(
                "\nВведите GT-ID, FP или SKIP: "
            ).strip().upper()

            if answer == "FP":

                false_positives += 1
                break

            if answer == "SKIP":

                excluded += 1
                break

            if answer in valid_ids:

                if answer in matched:

                    print("Повтор уже найденного дефекта.")
                    false_positives += 1

                else:

                    matched.add(answer)

                break

            print("Некорректный ID. Повторите ввод.")

    tp = len(matched)
    fp = false_positives
    fn = len(confirmed) - tp

    metrics = calculate_metrics(tp, fp, fn)

    metrics["excluded"] = excluded
    metrics["matched_ids"] = sorted(matched)
    metrics["missed_ids"] = sorted(
        valid_ids - matched
    )

    print("\n=== РЕЗУЛЬТАТЫ ОЦЕНКИ ===\n")

    print("True Positives:", tp)
    print("False Positives:", fp)
    print("False Negatives:", fn)
    print("Excluded:", excluded)

    print(f"Precision: {metrics['precision']:.2%}")
    print(f"Recall: {metrics['recall']:.2%}")
    print(f"F1-score: {metrics['f1_score']:.2%}")

    output = Path("evaluation/metrics.json")

    output.write_text(
        json.dumps(
            metrics,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    print("\nРезультаты сохранены:", output)


if __name__ == "__main__":

    cli = argparse.ArgumentParser()

    cli.add_argument("ground_truth")
    cli.add_argument("report")

    args = cli.parse_args()

    evaluate(
        args.ground_truth,
        args.report
    )

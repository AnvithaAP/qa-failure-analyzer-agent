"""Evaluate rule-based classifier performance on sample QA failure logs."""

from __future__ import annotations

import json
from pathlib import Path

from src.classifier import infer_category_from_rules
from src.utils import clean_log_text

DATASET_PATH = Path("examples/eval_dataset.json")


def main() -> None:
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))

    total = len(dataset)
    correct = 0

    print("[Step 1] Loading evaluation dataset...")
    print(f"Loaded {total} labeled examples from {DATASET_PATH}.")

    print("[Step 2] Running rule-based classification...")
    for item in dataset:
        log_path = Path(item["file"])
        expected = item["category"]
        log_text = clean_log_text(log_path.read_text(encoding="utf-8"))
        predicted = infer_category_from_rules(log_text) or "Test Issue"

        is_correct = predicted == expected
        correct += int(is_correct)

        status = "OK" if is_correct else "MISS"
        print(f"- {status}: {log_path.name} -> predicted={predicted}, expected={expected}")

    accuracy = correct / total if total else 0.0
    print("[Step 3] Reporting metrics...")
    print(f"classification_correct: {correct}/{total}")
    print(f"accuracy: {accuracy:.0%}")


if __name__ == "__main__":
    main()

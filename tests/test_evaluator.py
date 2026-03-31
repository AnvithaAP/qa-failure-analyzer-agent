from src.evaluator import evaluate


def test_evaluate_computes_accuracy_and_average_confidence():
    predictions = [
        {"category": "Test Issue", "confidence": 0.8},
        {"category": "Product Bug", "confidence": 0.6},
    ]
    truth = [{"category": "Test Issue"}, {"category": "Environment Issue"}]

    metrics = evaluate(predictions, truth)

    assert metrics["accuracy"] == 0.5
    assert metrics["avg_confidence"] == 0.7
    assert metrics["correct"] == 1
    assert metrics["total"] == 2

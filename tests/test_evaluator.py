from src.evaluator import evaluate


def test_evaluate_computes_advanced_metrics():
    predictions = [
        {"category": "Test Issue", "confidence": 0.8, "latency": 1.0},
        {"category": "Product Bug", "confidence": 0.6, "latency": 2.0},
        {"category": "Environment Issue", "confidence": 0.9, "latency": 1.5},
    ]
    truth = [
        {"category": "Test Issue"},
        {"category": "Environment Issue"},
        {"category": "Environment Issue"},
    ]

    metrics = evaluate(predictions, truth)

    assert metrics["accuracy"] == 2 / 3
    assert metrics["avg_confidence"] == (0.8 + 0.6 + 0.9) / 3
    assert metrics["avg_latency"] == (1.0 + 2.0 + 1.5) / 3
    assert metrics["per_category_accuracy"]["Test Issue"] == 1.0
    assert metrics["per_category_accuracy"]["Environment Issue"] == 0.5
    assert metrics["misclassifications"][0]["index"] == 2
    assert metrics["confusion"]["Environment Issue -> Product Bug"] == 1

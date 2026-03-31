from src.classifier import infer_category_from_rules, postprocess_analysis


def test_postprocess_analysis_normalizes_values():
    result = postprocess_analysis(
        {
            "root_cause": "Server returned 500",
            "category": "product",
            "confidence": 1.2,
            "suggestion": "Inspect backend error logs",
        }
    )

    assert result["category"] == "Product Bug"
    assert result["confidence"] == 1.0


def test_postprocess_analysis_defaults_for_missing_fields():
    result = postprocess_analysis({})

    assert result["category"] == "Test Issue"
    assert result["confidence"] == 0.5
    assert result["root_cause"]
    assert result["suggestion"]


def test_infer_category_from_rules_handles_common_failures():
    assert infer_category_from_rules("TimeoutError: API did not respond") == "Environment Issue"
    assert infer_category_from_rules("AssertionError: expected 1 got 2") == "Test Issue"
    assert infer_category_from_rules("HTTP 500 Internal Server Error") == "Product Bug"

from src.classifier import classify_failure, infer_category_from_rules, validate_output


def test_infer_category_from_rules_handles_common_failures():
    assert infer_category_from_rules("TimeoutError: API did not respond") == "Environment Issue"
    assert infer_category_from_rules("AssertionError: expected 1 got 2") == "Test Issue"
    assert infer_category_from_rules("HTTP 500 Internal Server Error") == "Product Bug"


def test_classify_failure_overrides_mismatched_llm_category():
    result = {
        "root_cause": "slow endpoint",
        "category": "Test Issue",
        "confidence": 0.2,
        "suggestion": "investigate",
    }
    out = classify_failure(result, "TimeoutError: API timed out")
    assert out["category"] == "Environment Issue"
    assert out["confidence"] >= 0.75


def test_validate_output_rejects_invalid_category():
    try:
        validate_output(
            {
                "root_cause": "x",
                "category": "Unknown",
                "confidence": 0.6,
                "suggestion": "y",
            }
        )
    except ValueError as exc:
        assert "Invalid category" in str(exc)
    else:
        raise AssertionError("Expected validate_output to raise ValueError")

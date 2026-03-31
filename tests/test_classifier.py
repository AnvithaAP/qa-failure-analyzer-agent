from src.classifier import classify_failure, infer_category_from_rules, validate_output


def test_infer_category_from_rules_handles_common_failures():
    assert infer_category_from_rules("TimeoutError: API did not respond") == "Environment Issue"
    assert infer_category_from_rules("AssertionError: expected 1 got 2") == "Test Issue"
    assert infer_category_from_rules("HTTP 500 Internal Server Error") == "Product Bug"
    assert infer_category_from_rules("ModuleNotFoundError: No module named 'x'") == "Dependency Issue"


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
    assert "keyword" in out["confidence_reason"] or "signal" in out["confidence_reason"]


def test_validate_output_normalizes_invalid_category_instead_of_raising():
    out = validate_output(
        {
            "root_cause": "x",
            "category": "environmental issue",
            "confidence": 0.6,
            "suggestion": "y",
        }
    )
    assert out["category"] == "Environment Issue"


def test_validate_output_accepts_and_defaults_latency():
    out = validate_output({"root_cause": "x", "category": "Test Issue", "confidence": 0.5, "suggestion": "y"})
    assert out["latency"] == 0.0
    assert out["confidence_reason"]

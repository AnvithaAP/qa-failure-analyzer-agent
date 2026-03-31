from src.classifier import postprocess_analysis


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

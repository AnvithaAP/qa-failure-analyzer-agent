from pathlib import Path

from src.memory import retrieve_similar, store_result


def test_memory_store_and_retrieve(tmp_path: Path):
    memory_path = tmp_path / "memory.json"
    log = "TimeoutError: API did not respond"
    result = {
        "root_cause": "API latency spike",
        "category": "Environment Issue",
        "confidence": 0.77,
        "suggestion": "Retry and inspect network",
        "latency": 1.1,
    }

    store_result(log, result, path=memory_path)
    matched = retrieve_similar(log, path=memory_path, threshold=0.8)

    assert matched is not None
    assert matched["category"] == "Environment Issue"


def test_memory_retrieve_allows_fuzzy_signature_matches(tmp_path: Path):
    memory_path = tmp_path / "memory.json"
    prior_log = "TimeoutError: API did not respond within 10s"
    new_log = "TimeoutError: API upstream did not respond within 10s"
    result = {
        "root_cause": "Network instability",
        "category": "Environment Issue",
        "confidence": 0.74,
        "suggestion": "Retry request",
        "latency": 0.9,
    }

    store_result(prior_log, result, path=memory_path)
    matched = retrieve_similar(new_log, path=memory_path, threshold=0.1)

    assert matched is not None
    assert matched["category"] == "Environment Issue"

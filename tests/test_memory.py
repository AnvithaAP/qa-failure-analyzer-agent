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

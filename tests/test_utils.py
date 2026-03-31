from src.utils import clean_log, truncate_log


def test_clean_log_removes_debug_and_timestamps():
    log_text = """2026-03-31 10:00:00 INFO start
2026-03-31 10:00:01 DEBUG noisy details
10:00:02 ERROR TimeoutError: API did not respond
"""

    cleaned = clean_log(log_text)

    assert "DEBUG" not in cleaned
    assert "2026-03-31" not in cleaned
    assert "TimeoutError" in cleaned


def test_truncate_log_shortens_large_input():
    large_log = "x" * 2000
    truncated = truncate_log(large_log, max_chars=100)

    assert len(truncated) > 100
    assert "TRUNCATED" in truncated

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

import agent


def test_should_retry_thresholds():
    assert agent.should_retry(0.59)
    assert not agent.should_retry(0.60)


def test_build_simplified_log_prefers_signal_lines():
    log = """INFO bootstrap
INFO user navigated
ERROR TimeoutError while calling /orders
INFO teardown
"""
    simplified = agent._build_simplified_log(log, max_chars=120)
    assert "ERROR TimeoutError" in simplified
    assert "bootstrap" not in simplified


def test_run_batch_outputs_summary(monkeypatch, tmp_path: Path, capsys):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "a.txt").write_text("A", encoding="utf-8")
    (logs_dir / "b.txt").write_text("B", encoding="utf-8")

    def fake_run_analysis(_: str, prompt_version: str = "v1", debug: bool = False, deterministic: bool = False) -> dict[str, object]:
        return {
            "root_cause": "x",
            "category": "Test Issue",
            "confidence": 0.8,
            "confidence_reason": "clear evidence",
            "suggestion": "y",
            "latency": 1.2,
            "metrics": {"latency": 1.2, "cost_estimate": 0.001},
            "steps": [],
        }

    monkeypatch.setattr(agent, "run_analysis", fake_run_analysis)
    outputs = agent.run_batch(logs_dir)

    assert len(outputs) == 2
    rendered = capsys.readouterr().out
    assert "Summary: processed=2" in rendered
    assert "category_breakdown={'Test Issue': 2}" in rendered


def test_run_ci_mode_generates_report(monkeypatch, tmp_path: Path):
    stream = tmp_path / "logs.txt"
    stream.write_text("ERROR timeout\n---\nERROR assertion", encoding="utf-8")

    monkeypatch.setattr(
        agent,
        "run_analysis",
        lambda *args, **kwargs: {
            "category": "Environment Issue",
            "confidence": 0.7,
            "metrics": {"latency": 0.2, "cost_estimate": 0.002},
            "steps": [],
        },
    )

    report = agent.run_ci_mode(stream)
    assert report["processed_logs"] == 2
    assert report["total_cost"] == 0.004

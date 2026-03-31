# QA Failure Analyzer Agent

A production-aware Python system that transforms QA logs into structured failure analysis with explicit role separation, evaluation introspection, prompt experimentation, and reproducible execution.

## Structured Output

```json
{
  "root_cause": "...",
  "category": "Product Bug | Test Issue | Environment Issue",
  "confidence": 0.0,
  "confidence_reason": "High confidence due to clear timeout pattern",
  "suggestion": "...",
  "latency": 0.0,
  "prompt_version": "v1"
}
```

## 🏗️ Where This Fits in QA Systems

This agent is designed to be a composable component in a broader QA platform:

- **CI/CD pipelines**: run after test jobs fail, classify failures, and produce machine-readable artifacts.
- **Test execution workflows**: consume Playwright/Cypress/JUnit/raw logs and normalize them into triage-ready output.
- **Failure triage systems**: route incidents to Jira/Slack/reporting dashboards with category + confidence metadata.

Example integration flow:

`Test Runner → Logs → Failure Analyzer → Jira / Reporting`

## System Roles

- **Analyzer (LLM)**: interprets logs with strict JSON output using versioned prompts in `prompts/`.
- **Classifier (rules)**: applies deterministic overrides for known failure signatures.
- **Evaluator**: reports quality metrics, per-error reasoning, hardest cases, and baseline comparisons.

This separation improves extensibility and makes behavior easier to tune and audit.

## Pipeline

`clean_log -> detect_error_events -> prioritize_critical_error -> (optional summarize) -> analyzer -> classifier -> validate_output -> memory`

Includes:
- multi-line log support (stack traces and continuation lines)
- multiple error detection in one log with severity-based prioritization
- truncated/partial log handling with confidence penalties
- confidence-based retry with stronger prompt behavior
- hybrid rule-based classification override
- validation guardrails and standardized latency field
- prompt version tracking (`prompt_version` in every output)
- caching + JSON memory for similar logs
- batch processing mode for real-world multi-log runs

## Configurable Categories

Categories are now loaded from `src/categories.json`.

You can add new categories without changing Python logic:

```json
{
  "categories": [
    "Product Bug",
    "Test Issue",
    "Environment Issue",
    "Dependency Issue"
  ]
}
```

## Project Structure

```bash
qa-failure-analyzer-agent/
├── src/
│   ├── agent.py
│   ├── llm.py
│   ├── classifier.py
│   ├── categories.json
│   ├── memory.py
│   ├── utils.py
│   └── evaluator.py
├── prompts/
│   ├── v1.txt
│   └── v2.txt
├── examples/
│   └── logs/
├── tests/
├── requirements.txt
└── evaluate.py
```

### ▶️ Quick Start

```bash
pip install -r requirements.txt
python src/agent.py --log "TimeoutError: API did not respond"
```

## CLI Usage

```bash
python src/agent.py --log "TimeoutError: API did not respond"
python src/agent.py --file examples/logs/timeout.txt
python src/agent.py --folder examples/logs/
python src/agent.py --ci-mode examples/sample_logs.txt
python src/agent.py --file examples/logs/assertion.txt --prompt v2 --debug
```

### CI Mode

`--ci-mode` ingests a single log stream file containing multiple failures (separated by `---`, `===`, or blank blocks), then:

- processes each failure block
- emits per-log structured results
- prints aggregate summary (category counts, average confidence/latency)
- reports **Avg Cost per log** and **Total Cost**

## Confidence & Cost Signals

Each analysis carries explicit confidence rationale:

- **Keyword match** (rule evidence strength)
- **LLM certainty** (model confidence output)
- **Rule overrides** (deterministic correction boosts)

Performance/cost awareness includes:

- approximate token usage (`token_estimate`)
- per-log cost estimate (`cost_estimate_usd`)
- run-level average/total cost in batch and evaluation runs

## 📊 Evaluation Metrics

Run:

```bash
python evaluate.py
```

The evaluation output includes:
- rule-only baseline accuracy vs LLM-agent accuracy improvement
- overall and per-category accuracy
- precision/recall per category
- average confidence, latency, and cost
- misclassification introspection
- top failure patterns + hardest cases

## ⚠️ Limitations

- LLM behavior can still drift despite strict formatting constraints.
- Cost estimation is approximate and model-price dependent.
- The included dataset is intentionally small and should be expanded for production confidence.

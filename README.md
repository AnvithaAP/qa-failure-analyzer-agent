# QA Failure Analyzer Agent

A production-aware Python system that turns noisy QA failure logs into structured, triage-ready analysis.

It combines **LLM reasoning** with **deterministic rule checks** so teams get both flexibility and consistency when classifying failures.

---

## Model Provider Support

This repository currently supports **OpenAI only** (`LLM_PROVIDER=openai`).

- Required env vars: `OPENAI_API_KEY`
- Optional env var: `OPENAI_MODEL` (default: `gpt-4o-mini`)

If you need Anthropic/local model support, extend `src/llm.py` with an additional provider client and preserve the same JSON output contract.

## Why This Matters

Traditional failure analysis in QA pipelines is often inefficient:

- Engineers manually scan long logs to find the likely root cause.
- Triage outcomes vary by person, context, and urgency.
- Repeated failure patterns are rediscovered instead of standardized.

This agent improves workflow quality by making failure analysis:

- **Faster**: automated first-pass classification reduces triage time.
- **More consistent**: normalized JSON output enforces a stable schema.
- **More scalable**: the same pipeline can run on one log or many logs from CI.

In practice: **manual analysis → slow and inconsistent**, while an **AI-assisted analyzer → faster, more standardized, and easier to operationalize**.

---

## 🔄 Before vs After

### Without Agent

- Manual log reading for each failure.
- High triage time and high context-switch cost.
- Inconsistent category labeling.
- Harder automation for Jira/Slack/reporting because output shape varies.

### With Agent

- Automated log cleaning, signal extraction, and classification.
- Faster debugging through structured root cause + suggestion fields.
- Standardized categories and confidence fields.
- Machine-readable JSON output ready for pipeline integrations.

---

## 🏗️ Where This Fits in QA Systems

This agent is designed as a composable component in a larger QA platform:

- **CI/CD pipelines**: run after test failures to classify incidents.
- **Test execution workflows**: process Playwright/Cypress/JUnit/raw logs.
- **Failure triage systems**: route incidents to Jira/Slack/dashboards.

**Integration flow:**

`Test Runner → Logs → Failure Analyzer → Jira / Reporting`

---

## System Roles

- **Analyzer (LLM)**: interprets logs using versioned prompts in `prompts/` and returns strict JSON.
- **Classifier (rules)**: applies deterministic keyword-based overrides for known failure signatures.
- **Evaluator**: reports quality metrics, hardest cases, and baseline comparisons.

This separation keeps the system easier to audit, tune, and evolve.

---

## ⚖️ Design Decisions & Tradeoffs

### Why hybrid (LLM + rules)

A hybrid approach captures semantic context (LLM) while preserving deterministic behavior for known patterns (rules).

### Why not rule-only

Rule-only systems are fast and cheap, but brittle. They miss nuanced failures and degrade when logs vary in wording or structure.

### Why JSON output

Structured JSON enables downstream automation (dashboards, alerts, ticketing, and analytics) without fragile parsing.

### Accuracy vs cost tradeoff

Higher reasoning depth can improve classification quality, but increases token usage and latency. This project explicitly surfaces `confidence`, `metrics.tokens`, and `metrics.cost_estimate` so teams can tune for their SLA and budget.

---

## Pipeline

`Input → Cleaning → LLM → Classification → Validation → Output`

Implemented flow:

`clean_log -> detect_error_events -> prioritize_critical_error -> (optional summarize) -> analyzer -> classifier -> validate_output -> memory`

Includes:

- multi-line log support (stack traces and continuation lines)
- sensitive-token redaction before LLM analysis (API keys, auth headers, emails, passwords)
- multiple error detection in one log with severity prioritization
- truncated/partial log handling with confidence penalties
- confidence-based retry with stronger prompt behavior
- hybrid rule-based classification override
- validation guardrails and standardized latency field
- prompt version tracking (`prompt_version` in each output)
- caching + JSON memory for similar logs
- batch processing mode for real-world multi-log runs

---

## 📊 What the Metrics Mean

### Accuracy

How often predicted categories match expected labels in the evaluation dataset.

### Confidence

Model-reported certainty (post-processed by rule signals and quality checks). Higher confidence suggests clearer evidence, not guaranteed correctness.

### When confidence is less reliable

Confidence should be treated cautiously when logs are truncated, partial, ambiguous, or contain overlapping failures. In those cases, confidence can be directionally useful but not definitive.

---

## ⚠️ When This May Fail

- Ambiguous logs without clear causal signals.
- Multiple overlapping errors where one symptom hides another root issue.
- LLM hallucinations or schema-compliant but incorrect reasoning.
- Small evaluation dataset size limiting confidence in generalization.

Use this tool as a triage accelerator, with human review for high-impact incidents.

---

## ▶️ Quick Demo

Run:

```bash
python src/agent.py --log "TimeoutError: API did not respond"
```

Example output:

```json
{
  "root_cause": "External API did not respond within expected timeout window.",
  "category": "Environment Issue",
  "confidence": 0.86,
  "confidence_reason": "Confidence combines keyword match, LLM certainty, and rule overrides; strongest signal='timeout' (severity=80).",
  "suggestion": "Verify network health, API availability, and retry policy configuration.",
  "latency": 0.123,
  "prompt_version": "v1",
  "token_estimate": 420,
  "cost_estimate_usd": 0.00021
}
```

---

## CLI Usage

```bash
python src/agent.py --log "TimeoutError: API did not respond"
python src/agent.py --file examples/logs/timeout.txt
python src/agent.py --folder examples/logs/
python src/agent.py --ci-mode examples/sample_logs.txt
python src/agent.py --file examples/logs/assertion.txt --prompt v2 --debug
python src/agent.py --file examples/logs/assertion.txt --no-cache
python src/agent.py --file examples/logs/assertion.txt --clear-cache
```

### CI Mode

`--ci-mode` ingests a single stream with multiple failures (separated by `---`, `===`, or blank blocks), then:

- processes each failure block
- emits per-log structured results
- prints aggregate summary (category counts, average confidence/latency)
- reports **Avg Cost per log** and **Total Cost**

---

## Configurable Categories

Categories are loaded from `src/categories.json`.

Example:

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

---

## 📈 Evaluation Metrics

Run:

```bash
python evaluate.py
```

The evaluation output includes:

- rule-only baseline accuracy vs hybrid-agent accuracy
- overall and per-category accuracy
- precision/recall per category
- average confidence, latency, and cost
- misclassification introspection and hardest cases

---

## 🚀 Future Work

- Integration with CI/CD and incident-management tools.
- Larger and more diverse dataset evaluation.
- Fine-tuned models for domain-specific failure signatures.
- Real-time monitoring and trend analytics over repeated failures.

---

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


---


## 🔒 Reliability Features

- Multi-stage fallback strategy: stronger prompt retry, summarized-log retry, deterministic rule fallback, and safe default.
- Input sanitization via `sanitize_input(log: str)` to strip prompt-injection patterns and suspicious command payloads.
- Deterministic mode (`--deterministic`) for reproducible outputs with low-variance LLM settings.
- Explicit edge-case handling for empty logs, very large logs, no-error-signal logs, and conflicting multi-error logs.

## 🔍 Explainability

- Full step trace emitted in `steps` for each run (`cleaning`, `llm_analysis`, `classification`, `validation`, plus fallback steps when used).
- Deterministic `reasoning` field in final output for auditability and incident triage trust.
- Version metadata attached to every output: `agent_version` and `prompt_version`.

## ⚙️ Production Readiness

- Machine-consumable JSON output with `--output result.json`.
- CI/CD summary report mode with `--ci-report`:
  - `total_logs`
  - `failures_detected`
  - `categories`
- Performance and cost visibility in `metrics`:
  - total latency
  - approximate token usage
  - estimated cost
- Added `stress_test.py` for robustness smoke checks on large logs, empty logs, random noise, and conflicting errors.

### New CLI examples

```bash
python src/agent.py --log "TimeoutError: API did not respond" --deterministic --output result.json
python src/agent.py --folder examples/logs --ci-report --output ci_report.json
python stress_test.py
```


## Privacy & Cost Guardrails

- Scrub credentials/tokens/PII from logs before sending to the LLM.
- Large logs are summarized to reduce prompt size and token spend.
- For strict data residency/security constraints, use this agent with a provider implementation that can run in your trusted environment.

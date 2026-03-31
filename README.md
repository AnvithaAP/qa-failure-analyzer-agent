# QA Failure Analyzer Agent

A production-aware Python system that transforms QA logs into structured failure analysis with explicit role separation, evaluation introspection, prompt experimentation, and reproducible execution.

## Structured Output

```json
{
  "root_cause": "...",
  "category": "Product Bug | Test Issue | Environment Issue",
  "confidence": 0.0,
  "suggestion": "...",
  "latency": 0.0,
  "prompt_version": "v1"
}
```

## System Roles

- **Analyzer (LLM)**: interprets logs with strict JSON output using versioned prompts in `prompts/`.
- **Classifier (rules)**: applies deterministic overrides for known failure signatures.
- **Evaluator**: reports quality metrics, per-error reasoning, and top failure patterns.

This separation improves extensibility and makes behavior easier to tune and audit.

## Pipeline

`clean_log -> (optional summarize) -> analyzer -> classifier -> validate_output -> memory`

Includes:
- log cleaning + truncation
- large-log summarization before analysis
- confidence-based retry with stronger prompt behavior
- confidence-based retry with simplified signal-only log fallback
- hybrid rule-based classification override
- validation guardrails and standardized latency field
- prompt version tracking (`prompt_version` in every output)
- caching + JSON memory for similar logs
- batch processing mode for real-world multi-log runs

## Project Structure

```bash
qa-failure-analyzer-agent/
├── src/
│   ├── agent.py
│   ├── llm.py
│   ├── classifier.py
│   ├── memory.py
│   ├── utils.py
│   └── evaluator.py
├── prompts/
│   ├── v1.txt
│   └── v2.txt
├── examples/
│   └── logs/
├── tests/
├── .env.example
├── requirements.txt
└── evaluate.py
```

### ▶️ Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env
python src/agent.py --log "TimeoutError: API did not respond"
```

## CLI Usage

```bash
python src/agent.py --log "TimeoutError: API did not respond"
python src/agent.py --file examples/logs/timeout.txt
python src/agent.py --folder examples/logs/
python src/agent.py --file examples/logs/assertion.txt --prompt v2
python src/agent.py --file examples/logs/assertion.txt --prompt v2 --debug
```

### Debug Mode (`--debug`)

When enabled, the system prints:
- raw LLM response
- parsed JSON payload
- classifier adjustments (including rule override reasons)

## 📊 Evaluation Metrics

Run:

```bash
python evaluate.py
```

The evaluation output includes:
- overall accuracy
- per-category accuracy
- average confidence and latency
- per-misclassification introspection (`Log`, `Expected`, `Predicted`, `Reason`)
- top failure patterns summary
- confusion totals

## 🧠 Design Decisions

- **Hybrid (LLM + rules)**: LLM gives flexible reasoning on noisy logs, while rules provide deterministic correction for high-frequency signatures.
- **JSON output contract**: strict machine-readable schema reduces downstream integration brittleness.
- **Retry logic**: low-confidence outcomes trigger a stronger prompt + simplified input retry to improve robustness on noisy or long logs.

## ⚠️ Limitations

- LLM behavior can still drift or hallucinate despite strict formatting constraints.
- The included evaluation dataset is small and should be expanded for production confidence.
- Rule-based keyword matching can introduce bias near category boundaries (e.g., timeout-related ambiguity).

## Trade-offs

- Similarity memory uses lightweight string similarity (fast, no extra infra) but can miss semantic matches.
- Summarization improves long-log handling but can hide minor details in very noisy traces.
- Prompt versioning increases control and experimentation options, but requires disciplined evaluation to avoid regressions.

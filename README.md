# QA Failure Analyzer Agent

A production-aware Python agent that transforms QA test logs into structured failure analysis with adaptive behavior, memory, and measurable performance.

## Structured Output

```json
{
  "root_cause": "...",
  "category": "Product Bug | Test Issue | Environment Issue",
  "confidence": 0.0,
  "suggestion": "...",
  "latency": 0.0
}
```

## Pipeline

`clean_log -> (optional summarize) -> analyze_log -> classify_failure -> validate_output -> memory`

Includes:
- log cleaning + truncation
- large-log summarization before analysis
- confidence-based retry with stronger prompt
- confidence-based retry with simplified signal-only log fallback
- hybrid rule-based classification override
- validation guardrails and standardized latency field
- caching + JSON memory for similar logs
- batch processing mode for real-world multi-log runs
- batch summary metrics (category mix, avg confidence, avg latency)

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
├── examples/
│   └── logs/
├── tests/
├── memory.json
├── requirements.txt
└── evaluate.py
```

## Setup

```bash
pip install -r requirements.txt
```

Set environment variables:

```env
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-4o-mini
```

## CLI Usage

```bash
python src/agent.py --log "TimeoutError: API did not respond"
python src/agent.py --file examples/logs/timeout.txt
python src/agent.py --folder examples/logs/
```

## 📊 Evaluation Metrics

The evaluation runner now reports:
- overall accuracy
- per-category accuracy (Product Bug, Test Issue, Environment Issue)
- misclassifications + confusion direction
- average confidence
- average latency

```bash
python evaluate.py
```

Example:

```text
Evaluation Results:
Overall Accuracy: 80%
Product Bug Accuracy: 75%
Test Issue Accuracy: 85%
Environment Issue Accuracy: 80%
Avg Latency: 1.200 seconds
```

## ⚙️ System Behavior

- **Adaptive retry logic:** if confidence < 0.6, the agent retries with a stronger system prompt.
- **Large-log handling:** if cleaned log length exceeds threshold, the log is summarized first.
- **Memory assist:** results are persisted to `memory.json`; similar logs can reuse previous classifications.
- **Observability:** runtime logs expose log length, summarization usage, retry trigger, final classification, and latency.

## ⏱ Performance

- Every output includes latency in seconds.
- Evaluation reports average latency across dataset samples.
- Batch mode prints overall average latency for processed logs.

## Tradeoffs

- Similarity memory uses lightweight string similarity (fast, no extra infra) but can miss semantic matches.
- Rule-based overrides improve precision for known patterns but may bias edge-case classifications.
- Summarization improves long-log handling but can hide minor details in very noisy traces.

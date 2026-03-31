# QA Failure Analyzer Agent

A production-like Python agent that transforms QA test logs into structured failure analysis with a reliable multi-step pipeline.

## Structured Output

```json
{
  "root_cause": "...",
  "category": "Product Bug | Test Issue | Environment Issue",
  "confidence": 0.0,
  "suggestion": "..."
}
```

## Pipeline

`clean_log -> analyze_log -> classify_failure -> validate_output -> output`

Includes:
- log cleaning + truncation
- strict JSON parsing with retry
- hybrid rule-based classification override
- validation guardrails
- caching and low-confidence warning

## Project Structure

```bash
qa-failure-analyzer-agent/
├── src/
│   ├── agent.py
│   ├── llm.py
│   ├── classifier.py
│   ├── utils.py
│   └── evaluator.py
├── examples/
│   └── logs/
│       ├── timeout.txt
│       ├── assertion.txt
│       ├── locator.txt
│       ├── api_error.txt
│       └── db_failure.txt
├── tests/
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
```

## Evaluation

```bash
python evaluate.py
```

Sample output:

```bash
Evaluation Results:
Accuracy: 80%
Correct: 4/5
Avg Confidence: 0.79
Total Samples: 5
```

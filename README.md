# QA Failure Analyzer Agent

A production-like Python agent that transforms test logs into structured failure analysis:

- `root_cause` (string)
- `category` (`Product Bug` | `Test Issue` | `Environment Issue`)
- `confidence` (float between 0 and 1)
- `suggestion` (string)

## Architecture

`Log -> Cleaning/Truncation -> LLM JSON -> Rule-based Classifier -> Post-processing -> Structured JSON`

## Project Structure

```
qa-failure-analyzer-agent/
├── src/
│   ├── agent.py
│   ├── llm.py
│   ├── classifier.py
│   └── utils.py
├── examples/
│   ├── timeout_failure.txt
│   ├── assertion_failure.txt
│   ├── locator_failure.txt
│   ├── db_failure.txt
│   ├── product_bug_failure.txt
│   └── eval_dataset.json
├── tests/
├── evaluate.py
├── requirements.txt
└── README.md
```

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Configure environment variables (e.g., `.env`):

```env
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-4o-mini
```

## CLI Usage

Analyze inline logs:

```bash
python src/agent.py --log "TimeoutError: API did not respond"
```

Analyze logs from file:

```bash
python src/agent.py --log-file examples/timeout_failure.txt
```

## Example Output

```json
{
  "root_cause": "API backend did not return within the expected timeout window.",
  "category": "Environment Issue",
  "confidence": 0.84,
  "suggestion": "Validate API health and increase timeout only after investigating backend latency."
}
```

## Evaluation

Run deterministic classification evaluation on labeled examples:

```bash
python evaluate.py
```

Example metrics:

```bash
classification_correct: 5/5
accuracy: 100%
```

## Agent Behaviors

The CLI provides transparent pipeline logging:

```bash
[Step 1] Cleaning logs...
[Step 2] Truncating logs for model context...
[Step 3] Sending logs to LLM...
[Step 4] Applying deterministic classifier override...
[Step 5] Normalizing final JSON payload...
```

## Notes

- Enforces structured output via OpenAI JSON mode and post-processing.
- Uses deterministic inference settings (`temperature=0`) for stable outputs.
- Includes hybrid LLM + rule-based classification behavior for reliability.

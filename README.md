# QA Failure Analyzer Agent

A production-like Python agent that transforms test logs into structured failure analysis:

- `root_cause` (string)
- `category` (`Product Bug` | `Test Issue` | `Environment Issue`)
- `confidence` (float between 0 and 1)
- `suggestion` (string)

## Architecture

`Log -> Cleaning/Truncation -> LLM -> Post-processing -> Structured JSON`

## Project Structure

```
qa-failure-analyzer-agent/
├── src/
│   ├── agent.py
│   ├── llm.py
│   ├── classifier.py
│   └── utils.py
├── examples/
│   └── sample_logs.txt
├── tests/
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
python src/agent.py --log-file examples/sample_logs.txt
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

## Prompt Design

System prompt used by the LLM module:

> You are a senior QA engineer analyzing test failures.
> Given logs, identify the root cause, classify the failure,
> and suggest actionable fixes.

User prompt shape:

```text
LOG:
<log_text>

Return JSON:
{
"root_cause": "...",
"category": "...",
"confidence": 0.0,
"suggestion": "..."
}
```

## Notes

- Includes error handling for empty input, missing API key, invalid JSON responses, and malformed categories.
- Uses deterministic inference settings (`temperature=0`) for stable outputs.

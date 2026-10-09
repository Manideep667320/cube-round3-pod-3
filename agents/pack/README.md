# Pack Manager — Round 3

Pack verifies the contents of an open merchant-fulfilled box before sealing.

## Decision boundary

The vision model **observes**. It does not decide `seal` or `stop_and_fix`.
Deterministic verification compares observed contents with trusted order lines:

- missing item → FAIL
- wrong/unexpected item → FAIL
- quantity mismatch → FAIL
- ambiguous/insufficient visual evidence → UNCERTAIN
- exact match → PASS / `seal`

Only `handle()` returns an Agent Output. The orchestrator remains the owner of workflow state.

## Input contract

Pack consumes the Round 3 Agent Input. Preferred order data is structured `order_lines` / `expected_items` in stage context or a JSON/CSV capture. The open-box image is supplied through `inputs[]`.

## Model policy

One batched vision call per unit. The model returns observations only. Model failure is fail-open: a `pending` / `UNCERTAIN` evidence record is returned rather than claiming success.

## Local run

From the Pod repository:

```bash
python -m pytest tests/integration/test_agent_contracts.py -q
.venv/bin/uvicorn agents.pack.app:app --port 8103
```

Set `OPENAI_API_KEY` and optionally `PACK_MODEL=gpt-4.1-mini`.

Do not copy a second `shared/` or `orchestration/` implementation into this folder.

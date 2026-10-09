# Provenance

- **Owner:** Gayathri (@gayathri2665)
- **No Round 2 source repository was used.** This agent was written from scratch on top
  of the Round 3 starter's organiser stub in this repository (`agents/receiving/app.py`,
  CSV-replay stub, `agent_id: receiving-stub@0`).
- Starter baseline when work began: repo `HEAD` `efe30c5` ("feat: implement recovery agent…"),
  i.e. the stub as delivered by the organiser fork (`ab72b24`).
- Behavioural requirements came from this repo's own contract documents:
  `EVIDENCE-CONTRACT.md` v1.0, `INTEGRATION-GUIDE.md`, `shared/schemas/*.schema.json`,
  and the plan reviewed on 2026-10-09 (retake coach, verdict card, eight review gaps).
- Round 2 sample data (`data/sample/receiving_sample.csv`) is the **organiser's synthetic
  CSV**; it seeds the manifest only. The agent does not read verdict columns from it —
  verdicts come from photos, operator inputs and the manifest line.
- Benchmark evaluation is conducted directly over the canonical 100 sample units
  in `data/sample/receiving_sample.csv` via `python -m agents.receiving.eval`.
- Barcode encoding for test fixtures uses `python-barcode`; decoding uses `zxing-cpp`.

# Alert Noise Analyzer — Project Plan

## 1. Purpose

Two goals, both real:

1. **Model/tool evaluation** — get hands-on with OpenCode + Nemotron 3 Ultra on a multi-file, multi-session build, to see if it holds up on planning, tool use, and iterative debugging across turns (not just one-shot script generation).
2. **Portfolio artifact** — build something that mirrors real, validated SRE pain points (recurring alert noise, correlated alerts, bad thresholds, missing runbooks) using entirely synthetic data, so it's safe to demo to Ngoc or anyone else without touching anything Halliburton owns.

This is explicitly a **water-testing POC**. No production wiring, no live API calls to real systems, no scheduling, no approval needed from anyone. If it turns out useful, the "how would this become real" conversation happens later, with the right people, not now.

## 2. What "done" looks like

A CLI tool that:
- Takes a synthetic alert dataset (JSON or CSV) as input
- Runs four independent analyses over it
- Outputs one readable weekly report (terminal + optionally markdown file)

Something you could screen-share in under 5 minutes and have it make sense to someone who's seen a real on-call dashboard.

## 3. Scope

**In scope:**
- Synthetic data generator (so the tool has realistic patterns to actually find)
- Four detectors: recurring patterns, correlated alerts, threshold sanity, runbook coverage gaps
- One consolidated report generator
- A CLI entrypoint
- Basic tests proving each detector catches what it's supposed to catch

**Out of scope (for this POC):**
- Any real New Relic, ADO, or Salesforce API calls
- Any real Halliburton data, account IDs, or credentials
- Scheduling / running continuously
- A UI beyond terminal output
- Remediation *execution* (this only ever suggests/reports, never acts)

## 4. Data model (synthetic, but realistic)

Mirrors the shape of the `globalNrAiIssue` schema you already know, so the logic would transfer if this ever got pointed at something real later:

```json
{
  "violation_id": "string",
  "policy": "string",           // e.g. "HAL-NR-P0007"
  "condition": "string",        // e.g. "DWP-MIDDLEWARE Response Time"
  "priority": "P1 | P2 | P3",
  "entity_name": "string",
  "entity_type": "string",      // e.g. "APM Service", "Host", "Gateway"
  "account_id": "string",
  "opened_at_utc": "ISO8601",
  "closed_at_utc": "ISO8601 | null",
  "threshold_value": "number | null",
  "observed_value": "number | null",
  "description": "string"
}
```

Runbook coverage uses a second small synthetic file: a list of `policy` → `runbook_url` mappings, deliberately incomplete (some policies have none, like your HAL-NR-P0007 finding).

## 5. Synthetic data generator — design

This is the part that makes the rest of the project meaningful. Random noise won't exercise the detectors properly — the generator needs to **deliberately seed** the patterns you already know are real:

- **Recurring pattern**: pick 5-10 condition+account pairs, fire them repeatedly (5+ times) over a 7-day synthetic window
- **Correlated cluster**: seed 2-3 alert chains that fire within minutes of each other (mirroring your Host Down → Gateway → AWX Job case) — same rough timestamp, different entities
- **Bad threshold**: for a couple of conditions, generate observed values that cluster well below/above the configured threshold, so a tuning recommendation is obviously correct
- **Alert storm**: seed one burst — 15-20 alerts within a short window, different conditions, same account
- **Background noise**: the rest is random, non-patterned alerts, so detectors have to actually find the signal, not just report everything

## 6. Architecture / module breakdown

```
alert-noise-analyzer/
├── generator/
│   └── synthetic_data.py       # produces alerts.json + runbooks.json
├── analyzers/
│   ├── recurring.py            # condition+account frequency over time window
│   ├── correlation.py          # time-clustering across entities
│   ├── threshold.py            # observed vs configured threshold stats
│   └── runbook_coverage.py     # policy -> runbook cross-reference
├── report/
│   └── report_generator.py     # consolidates all 4 into one output
├── tests/
│   └── test_analyzers.py       # known-pattern fixtures, assert detection
├── cli.py                      # argparse entrypoint, wires it all together
└── README.md
```

## 7. Detector logic (plain-language, no need to overthink the algorithms)

- **Recurring**: group by (condition, account_id), count occurrences within a rolling N-day window, flag anything over a configurable threshold (default: 5 in 7 days — matches what you found manually)
- **Correlation**: sort all alerts by `opened_at_utc`, sliding window of a few minutes, group alerts that fall in the same window across different entities as a "likely single incident" cluster
- **Threshold sanity**: for conditions with enough historical `observed_value` data, compare median observed value against `threshold_value` — flag if the threshold is set well outside the normal operating range (over- or under-sensitive)
- **Runbook coverage**: simple set difference — policies present in alert data but absent from the runbook mapping file

## 8. Output

A single weekly report, e.g.:

```
ALERT NOISE REPORT — Week of Aug 10-17
========================================
Recurring Noise (5+ in 7 days): 6 condition/account pairs
Likely Single-Incident Clusters: 3
Threshold Tuning Candidates: 2
Policies Missing Runbooks: 4

[details per section...]
```

Terminal output by default, `--markdown` flag to write a `.md` file too.

## 9. Tech stack

- Python 3.11+, stdlib mostly (argparse, json, datetime)
- `pandas` optional if grouping logic gets messy — otherwise skip the dependency
- No external network calls at all — fully offline, fully synthetic

## 10. Build plan (incremental, each step = a real commit)

1. **Scaffolding + synthetic data generator** — get `generator/synthetic_data.py` producing realistic alerts.json with seeded patterns
2. **Recurring pattern detector** — smallest, most self-contained detector, good first real logic commit
3. **Correlation detector** — the trickiest logic, worth its own session/commit
4. **Threshold + runbook coverage detectors** — smaller, can go together
5. **Report generator + CLI wiring** — brings it all together into one runnable tool
6. **Tests** — fixtures with known seeded patterns, assert each detector catches them
7. **README + polish** — makes it demoable

This also happens to be a good test of Nemotron/OpenCode's ability to hold context across a multi-session, multi-file build — which is the other thing you wanted to evaluate.

## 11. How to judge if the model/tool combo is actually good

Worth tracking as you go, since this is also an eval exercise:
- Does it remember earlier files/decisions across sessions, or does it contradict itself?
- Does it ask clarifying questions when the spec is ambiguous, or guess silently?
- When a test fails, does it actually debug the root cause or just patch symptoms?
- How many turns/tool calls does each step take vs. what you'd estimate for Claude Code on the same task?
- Any hallucinated library usage or made-up APIs?

## 11a. Real-data readiness (important — read before claiming this "works")

Two separate claims, don't conflate them:

- **"The architecture would accept real data without a rewrite"** — this is something we design for and can honestly claim once built.
- **"The detection logic is accurate on real data"** — this can NOT be claimed until it's actually run against real or realistically messy data. Clean synthetic data proves the logic runs, not that it's right. Keep these separate in any conversation about this project, including with Ngoc.

To make the first claim true:

1. **Loader abstraction** — analyzers consume a normalized list of alert objects, never a file path directly. `generator/synthetic_data.py` is one interchangeable loader; a future `loaders/new_relic_api.py` would be another. Detectors don't change either way.
2. **Schema matches the real `globalNrAiIssue` shape exactly** — same field names, types, nullability — not a simplified version, so nothing breaks on first contact with a real field.
3. **Defensive parsing from day one, not bolted on later**:
   - `closed_at_utc` can be null (still-open alerts) — every detector must handle open + closed alerts correctly
   - Occasional missing/malformed fields — don't crash, log and skip or flag
   - Duplicate `violation_id`s — dedupe logic, don't double-count
   - Out-of-order timestamps — never assume the input list is sorted
4. **Seeded messiness in the synthetic generator itself, not just clean seeded patterns** — a percentage of records get nulls, duplicates, and out-of-order timestamps injected deliberately, on top of the seeded patterns from section 5, so the detectors are forced to prove they handle it now, while it's cheap, instead of discovering it later against real data.
5. **Configurable thresholds, not magic numbers** — recurring-count threshold, correlation time-window, etc. are parameters. Real-world tuning will differ from whatever works on synthetic data, and that's expected, not a bug.

## 12. Risks / honest limitations

- Synthetic data means detection quality here doesn't prove it'd work on messy real data in terms of *accuracy* — it proves the architecture and defensive handling are sound, not that the thresholds/heuristics are correct for real-world volumes
- Correlation-by-time-proximity is a naive heuristic; real correlation would need topology/service-dependency awareness, which is a much bigger project
- This is intentionally not wired to anything live — turning it into something real is a separate conversation with actual owners (Ngoc, Satish) and actual approval

## 13. If it's ever worth scaling later (not now)

Would require: real New Relic API access via the centralized account, a human decision-maker sponsoring it, a place to actually run it (not your laptop), and someone besides you validating the correlation logic against real incidents. None of that is this project's problem right now.

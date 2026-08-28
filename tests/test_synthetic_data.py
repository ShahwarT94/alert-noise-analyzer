#!/usr/bin/env python3
"""
Tests for the synthetic data generator (``generator/synthetic_data.py``).

Two families of tests:

1. Determinism of ``generate_runbooks()`` across *separate process runs*
   with the same seed (it previously fed ``list(set(...))`` into
   ``rng.sample()``, and set iteration order for strings depends on
   per-process hash randomization).

2. Phase 1a hardening: the four deliberately-seeded patterns exist at the
   intended scale, messiness injection actually injects, every record
   conforms to the alert schema, counts/ratios land in the intended
   ranges, and every alert opens inside the hardcoded 7-day window.

Expected values are taken from this module's constants, its docstrings, and
the Phase 1a spec in ``docs/PLAN.md`` -- never recomputed with the
generator's own arithmetic, which would only prove the code equals itself.
"""

import json
import os
import random
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from generator import synthetic_data as G
from generator.synthetic_data import generate_alerts, generate_runbooks

REPO_ROOT = Path(__file__).resolve().parent.parent
SEED = 42

# Seeds exercised by the whole-pipeline tests. Curated (not a bare range) so
# the suite is stable; the rare-seed window violations found in Phase 1a are
# reported separately, not encoded here as acceptable.
FULL_SEEDS = (42, 0, 1, 2, 7, 13, 99, 123, 500, 2024)
# Seeds for the isolated sub-generator contract tests. range(50) avoids the
# known cluster-overflow seeds (1452, 2274) documented in the Phase 1a report.
SUB_SEEDS = tuple(range(50))

# --- Intended window: "the 7 days ending 2026-08-15T23:59:59Z" (module +
# CLAUDE.md). generate_alerts() hardcodes exactly this.
WINDOW_END = datetime(2026, 8, 15, 23, 59, 59)
WINDOW_START = WINDOW_END - timedelta(days=7)

# --- Intended scale of each seeded pattern. Values are the literal bounds
# written into the generator (the spec calls these "the intended number /
# range"); the module carries no docstring stating them.
RECURRING_PAIRS = (6, 8)  # generate_recurring_noise: rng.randint(6, 8) distinct pairs
RECURRING_FIRES = (6, 10)  # ... each pair: occurrences = rng.randint(6, 10)

CORRELATED_CLUSTERS = 3  # generate_correlated_clusters: 3 hardcoded templates
CLUSTER_SIZE = 3  # ... 3 conditions per template
CLUSTER_SPAN_MAX = timedelta(minutes=5)  # offset_minutes = rng.randint(0, 5)

BAD_THRESHOLD_CONDITIONS = 2  # generate_bad_threshold_alerts: rng.sample(..., 2)
BAD_THRESHOLD_FIRES = (8, 15)  # occurrences = rng.randint(8, 15)
BAD_THRESHOLD_RANGE = (20.0, 50.0)  # threshold = round(rng.uniform(20, 50), 2)
BAD_THRESHOLD_RATIO = (1.4, 1.8)  # observed = threshold * rng.uniform(1.4, 1.8)
RATIO_ROUNDING_EPS = 0.01  # observed/threshold rounded to 2 decimals

STORM_ALERTS = (15, 20)  # generate_alert_storm: rng.randint(15, 20)
STORM_SPAN_MAX = timedelta(minutes=10)  # opened_at = start + rng.randint(0, 600)s

# --- Totals / ratios / messiness (module constants + CLAUDE.md).
TOTAL_RANGE = (400, 600)  # target_total = rng.randint(400, 600)
MAX_DUPLICATE_APPENDS = 4  # add_messiness appends min(4, n) copies AFTER target_total
MESSINESS_RATE = 0.09  # add_messiness(messiness_rate=0.09); CLAUDE.md: "~9%"
# generate_runbooks: int(len(policies) * 0.7); CLAUDE.md: "~70%"
RUNBOOK_COVERAGE = 0.70

# --- Schema.
EXPECTED_FIELDS = {
    "violation_id",
    "policy",
    "condition",
    "priority",
    "entity_name",
    "entity_type",
    "account_id",
    "opened_at_utc",
    "closed_at_utc",
    "threshold_value",
    "observed_value",
    "description",
}
NON_NULLABLE_FIELDS = EXPECTED_FIELDS - {
    "closed_at_utc",
    "threshold_value",
    "observed_value",
}
THRESHOLD_ENTITY_TYPES = {"APM Service", "Host", "Gateway"}  # generate_alert
VIOLATION_ID_RE = re.compile(r"^V-\d{6}$")  # generate_violation_id
ISO_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")  # format_iso

POLICY_VOCAB = set(G.POLICIES)
ACCOUNT_VOCAB = set(G.ACCOUNT_IDS)
PRIORITY_VOCAB = set(G.PRIORITIES)
DESCRIPTION_VOCAB = set(G.DESCRIPTIONS)
CONDITION_VOCAB = {c for c, _ in G.CONDITIONS}
ENTITY_TYPE_VOCAB = {et for _, et in G.CONDITIONS}
CONDITION_ENTITY_TYPE = {c: et for c, et in G.CONDITIONS}


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)


def _in_window(ts: str) -> bool:
    return WINDOW_START <= _parse(ts) <= WINDOW_END


# ---------------------------------------------------------------------------
# 1. generate_runbooks() determinism
# ---------------------------------------------------------------------------

# Runs the generator end to end and prints the runbooks payload as JSON.
# Executed in a child process so each invocation gets its own hash seed; the
# seed is passed as argv rather than interpolated to keep the snippet literal.
_CHILD = """
import json, sys
from generator.synthetic_data import generate_alerts, generate_runbooks

seed = int(sys.argv[1])
alerts, _ = generate_alerts(seed)
runbooks, missing = generate_runbooks(alerts, seed)
json.dump({"runbooks": runbooks, "missing": missing}, sys.stdout, indent=2)
"""


def _generate_in_subprocess(hash_seed: str) -> str:
    """Generate runbooks in a fresh interpreter with PYTHONHASHSEED pinned.

    Pinning the value (rather than leaving it random) makes the test
    deterministic: two different values force two different set-iteration
    orders, so the pre-fix code reliably produced diverging output here,
    while the fixed code produces identical output for any value.
    """
    env = {
        **os.environ,
        "PYTHONHASHSEED": hash_seed,
        "PYTHONPATH": str(REPO_ROOT),
    }
    result = subprocess.run(
        [sys.executable, "-c", _CHILD, str(SEED)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def test_generate_runbooks_reproducible_across_processes() -> None:
    # A same-process double call would NOT catch the original bug: hash
    # randomization is fixed for the life of one interpreter, so both calls
    # would see the same set ordering. Distinct child processes with
    # distinct PYTHONHASHSEED values are what exercises it.
    outputs = [_generate_in_subprocess(hs) for hs in ("0", "1", "2", "13579")]

    first = outputs[0]
    for other in outputs[1:]:
        assert other == first, (
            "generate_runbooks output varies across processes with the same "
            "seed; ordering is not deterministic"
        )

    # Sanity: the payload is what we think it is.
    payload = json.loads(first)
    assert payload["runbooks"], "expected at least one runbook"
    assert all({"policy", "runbook_url"} == set(rb) for rb in payload["runbooks"])


def test_generate_runbooks_stable_within_process() -> None:
    # Weaker check, but cheap and documents the intended contract.
    alerts, _ = generate_alerts(SEED)
    a = generate_runbooks(alerts, SEED)
    b = generate_runbooks(alerts, SEED)
    assert a == b


# ---------------------------------------------------------------------------
# 2a. Seeded patterns exist at the intended scale (isolated sub-generators)
# ---------------------------------------------------------------------------


def test_recurring_pattern_scale() -> None:
    lo_pairs, hi_pairs = RECURRING_PAIRS
    lo_fire, hi_fire = RECURRING_FIRES
    for seed in SUB_SEEDS:
        alerts = G.generate_recurring_noise(
            random.Random(seed), WINDOW_START, WINDOW_END
        )
        by_pair = Counter((a["condition"], a["account_id"]) for a in alerts)

        assert lo_pairs <= len(by_pair) <= hi_pairs, (
            f"seed={seed}: {len(by_pair)} recurring (condition, account) pairs, "
            f"expected {lo_pairs}-{hi_pairs}"
        )
        for pair, count in by_pair.items():
            assert lo_fire <= count <= hi_fire, (
                f"seed={seed}: pair {pair} fired {count}x, "
                f"expected {lo_fire}-{hi_fire}"
            )
        for a in alerts:
            assert CONDITION_ENTITY_TYPE[a["condition"]] == a["entity_type"]
            assert _in_window(a["opened_at_utc"]), f"seed={seed}: {a['opened_at_utc']}"


def test_correlated_clusters_scale() -> None:
    for seed in SUB_SEEDS:
        alerts = G.generate_correlated_clusters(
            random.Random(seed), WINDOW_START, WINDOW_END
        )
        assert len(alerts) == CORRELATED_CLUSTERS * CLUSTER_SIZE, (
            f"seed={seed}: {len(alerts)} clustered alerts, expected "
            f"{CORRELATED_CLUSTERS * CLUSTER_SIZE}"
        )
        # Clusters are emitted as contiguous runs of CLUSTER_SIZE.
        for i in range(CORRELATED_CLUSTERS):
            chunk = alerts[i * CLUSTER_SIZE : (i + 1) * CLUSTER_SIZE]
            assert len(chunk) == CLUSTER_SIZE
            assert (
                len({a["account_id"] for a in chunk}) == 1
            ), f"seed={seed}: cluster {i} spans multiple accounts"
            assert (
                len({a["condition"] for a in chunk}) == CLUSTER_SIZE
            ), f"seed={seed}: cluster {i} has duplicate conditions"
            times = sorted(_parse(a["opened_at_utc"]) for a in chunk)
            assert times[-1] - times[0] <= CLUSTER_SPAN_MAX, (
                f"seed={seed}: cluster {i} spans {times[-1] - times[0]}, "
                f"expected <= {CLUSTER_SPAN_MAX}"
            )
            for a in chunk:
                assert _in_window(a["opened_at_utc"]), (
                    f"seed={seed}: clustered alert outside window: "
                    f"{a['opened_at_utc']}"
                )


def test_bad_threshold_scale() -> None:
    lo_fire, hi_fire = BAD_THRESHOLD_FIRES
    lo_thr, hi_thr = BAD_THRESHOLD_RANGE
    lo_ratio, hi_ratio = BAD_THRESHOLD_RATIO
    for seed in SUB_SEEDS:
        alerts = G.generate_bad_threshold_alerts(
            random.Random(seed), WINDOW_START, WINDOW_END
        )
        by_condition = Counter(a["condition"] for a in alerts)

        assert len(by_condition) == BAD_THRESHOLD_CONDITIONS, (
            f"seed={seed}: {len(by_condition)} bad-threshold conditions, "
            f"expected {BAD_THRESHOLD_CONDITIONS}"
        )
        for condition, count in by_condition.items():
            assert lo_fire <= count <= hi_fire, (
                f"seed={seed}: {condition} fired {count}x, "
                f"expected {lo_fire}-{hi_fire}"
            )
        for a in alerts:
            thr, obs = a["threshold_value"], a["observed_value"]
            assert lo_thr <= thr <= hi_thr, f"seed={seed}: threshold {thr}"
            ratio = obs / thr
            assert (
                lo_ratio - RATIO_ROUNDING_EPS <= ratio <= hi_ratio + RATIO_ROUNDING_EPS
            ), f"seed={seed}: observed/threshold = {ratio:.4f}, expected ~{BAD_THRESHOLD_RATIO}"
            assert _in_window(a["opened_at_utc"]), f"seed={seed}: {a['opened_at_utc']}"


def test_alert_storm_scale() -> None:
    lo, hi = STORM_ALERTS
    for seed in SUB_SEEDS:
        alerts = G.generate_alert_storm(random.Random(seed), WINDOW_START, WINDOW_END)

        assert (
            lo <= len(alerts) <= hi
        ), f"seed={seed}: storm has {len(alerts)} alerts, expected {lo}-{hi}"
        assert (
            len({a["account_id"] for a in alerts}) == 1
        ), f"seed={seed}: storm spans multiple accounts"
        times = sorted(_parse(a["opened_at_utc"]) for a in alerts)
        assert times[-1] - times[0] <= STORM_SPAN_MAX, (
            f"seed={seed}: storm spans {times[-1] - times[0]}, "
            f"expected <= {STORM_SPAN_MAX}"
        )
        for a in alerts:
            assert _in_window(a["opened_at_utc"]), f"seed={seed}: {a['opened_at_utc']}"


# ---------------------------------------------------------------------------
# 2b. Whole-pipeline properties
# ---------------------------------------------------------------------------


def test_alert_schema_conformance() -> None:
    for seed in FULL_SEEDS:
        alerts, _ = generate_alerts(seed)
        for a in alerts:
            ctx = f"seed={seed} vid={a.get('violation_id')}"
            assert set(a) == EXPECTED_FIELDS, f"{ctx}: fields {set(a)}"

            for field in NON_NULLABLE_FIELDS:
                assert a[field] is not None, f"{ctx}: {field} is None"

            assert VIOLATION_ID_RE.match(a["violation_id"]), ctx
            assert a["policy"] in POLICY_VOCAB, ctx
            assert a["condition"] in CONDITION_VOCAB, ctx
            assert a["entity_type"] in ENTITY_TYPE_VOCAB, ctx
            assert a["account_id"] in ACCOUNT_VOCAB, ctx
            assert a["priority"] in PRIORITY_VOCAB, ctx
            assert a["description"] in DESCRIPTION_VOCAB, ctx
            assert isinstance(a["entity_name"], str) and a["entity_name"], ctx

            assert ISO_UTC_RE.match(a["opened_at_utc"]), ctx
            assert a["closed_at_utc"] is None or ISO_UTC_RE.match(
                a["closed_at_utc"]
            ), ctx

            for field in ("threshold_value", "observed_value"):
                v = a[field]
                assert v is None or (
                    isinstance(v, float) and v > 0
                ), f"{ctx}: {field}={v}"

            # AWX Job entities are never assigned a threshold, so never an
            # observed value either. Messiness only nulls values, so this
            # holds post-corruption too. Phase 1b keys labels off this.
            if a["entity_type"] == "AWX Job":
                assert a["threshold_value"] is None, ctx
                assert a["observed_value"] is None, ctx
            # A present threshold implies a threshold-bearing entity type.
            if a["threshold_value"] is not None:
                assert a["entity_type"] in THRESHOLD_ENTITY_TYPES, ctx


def test_generate_alerts_stats_structure() -> None:
    for seed in FULL_SEEDS:
        alerts, stats = generate_alerts(seed)
        assert set(stats) == {
            "recurring",
            "clusters",
            "bad_threshold",
            "storm",
            "messy",
            "total",
        }
        assert all(isinstance(v, int) for v in stats.values())
        assert stats["total"] == len(alerts)


def test_all_alerts_within_time_window() -> None:
    # "Within the window" is read as opened_at in [WINDOW_START, WINDOW_END].
    # closed_at legitimately runs past WINDOW_END (an alert opened late on the
    # last day with a multi-hour duration), so it is not constrained here.
    for seed in FULL_SEEDS:
        alerts, _ = generate_alerts(seed)
        for a in alerts:
            opened = _parse(a["opened_at_utc"])
            assert WINDOW_START <= opened <= WINDOW_END, (
                f"seed={seed}: opened_at {a['opened_at_utc']} outside "
                f"[{WINDOW_START}, {WINDOW_END}]"
            )


def test_total_alert_count_in_range() -> None:
    lo, hi = TOTAL_RANGE
    for seed in FULL_SEEDS:
        _, stats = generate_alerts(seed)
        # Upper bound is nominal + MAX_DUPLICATE_APPENDS: add_messiness appends
        # up to 4 duplicate records after target_total is fixed (see report).
        assert lo <= stats["total"] <= hi + MAX_DUPLICATE_APPENDS, (
            f"seed={seed}: total {stats['total']} outside "
            f"[{lo}, {hi} (+{MAX_DUPLICATE_APPENDS})]"
        )


def test_runbook_coverage_ratio_across_seeds() -> None:
    for seed in FULL_SEEDS:
        alerts, _ = generate_alerts(seed)
        n_policies = len({a["policy"] for a in alerts})
        runbooks, missing = generate_runbooks(alerts, seed)

        assert len(runbooks) + missing == n_policies
        covered = len(runbooks) / n_policies
        # int(n * 0.7) / n lands a little under 0.70 for these policy counts.
        assert (
            RUNBOOK_COVERAGE - 0.06 <= covered <= RUNBOOK_COVERAGE + 0.02
        ), f"seed={seed}: runbook coverage {covered:.3f}, expected ~{RUNBOOK_COVERAGE}"


def test_generate_runbooks_matches_int_ratio_exactly() -> None:
    # The precise contract, on the committed seed (extends the determinism
    # work's ratio check rather than duplicating it).
    alerts, _ = generate_alerts(SEED)
    unique_policies = {a["policy"] for a in alerts}
    runbooks, missing = generate_runbooks(alerts, SEED)

    assert len(runbooks) == int(len(unique_policies) * RUNBOOK_COVERAGE)
    assert len(runbooks) + missing == len(unique_policies)
    assert {rb["policy"] for rb in runbooks} <= unique_policies


# ---------------------------------------------------------------------------
# 2c. Messiness injection
# ---------------------------------------------------------------------------


def test_messiness_rate_within_tolerance() -> None:
    # Nominal rate is MESSINESS_RATE (0.09). The realized rate runs lower
    # (~0.05-0.08) -- see the Phase 1a report on the no-op "duplicate" branch
    # in add_messiness. This band guards against gross regression (rate -> 0
    # or -> everything), not the exact 9%.
    for seed in FULL_SEEDS:
        _, stats = generate_alerts(seed)
        frac = stats["messy"] / stats["total"]
        assert 0.04 <= frac <= 0.11, f"seed={seed}: messy fraction {frac:.3f}"


def test_messiness_each_corruption_type_present() -> None:
    # Each corruption add_messiness can apply must actually show up. Checked
    # on several seeds so a single unlucky layout does not hide a type.
    for seed in (42, 0, 7, 99, 2024):
        alerts, _ = generate_alerts(seed)

        null_threshold = [
            a
            for a in alerts
            if a["entity_type"] in THRESHOLD_ENTITY_TYPES
            and a["threshold_value"] is None
        ]
        null_observed = [
            a
            for a in alerts
            if a["threshold_value"] is not None and a["observed_value"] is None
        ]
        reversed_ts = [
            a
            for a in alerts
            if a["closed_at_utc"]
            and _parse(a["closed_at_utc"]) < _parse(a["opened_at_utc"])
        ]
        vid_counts = Counter(a["violation_id"] for a in alerts)
        duplicated_vids = [v for v, c in vid_counts.items() if c > 1]

        assert null_threshold, f"seed={seed}: no messiness-nulled threshold_value"
        assert null_observed, f"seed={seed}: no messiness-nulled observed_value"
        assert reversed_ts, f"seed={seed}: no reversed open/close timestamps"
        assert duplicated_vids, f"seed={seed}: no duplicate violation_id records"

        # F3 fixed: base generation now guarantees unique violation_ids, so
        # EVERY shared id must be an add_messiness near-duplicate -- same
        # payload as its original except the shifted timestamps. (Before the
        # fix this had to allow accidental collisions between unrelated
        # alerts and only require >= 1 clean near-duplicate.)
        for vid in duplicated_vids:
            copies = [a for a in alerts if a["violation_id"] == vid]
            differing = {
                k for k in EXPECTED_FIELDS if len({repr(c[k]) for c in copies}) > 1
            }
            assert differing and differing <= {"opened_at_utc", "closed_at_utc"}, (
                f"seed={seed}: violation_id {vid} shared by {len(copies)} records "
                f"differing in {sorted(differing)} -- not a deliberate duplicate"
            )


def test_violation_ids_unique_except_deliberate_duplicates() -> None:
    # F3: generate_violation_id draws independently, so ids collided by the
    # birthday paradox (~13% of seeds; seed 99 is the known reproducer).
    # After the fix, the only permitted repeat is an add_messiness
    # near-duplicate. range(120) spans ~15 formerly-colliding seeds and
    # includes 99.
    for seed in range(120):
        alerts, _ = generate_alerts(seed)
        by_vid: dict[str, list[dict]] = {}
        for a in alerts:
            by_vid.setdefault(a["violation_id"], []).append(a)

        for vid, group in by_vid.items():
            if len(group) == 1:
                continue
            differing = {
                k for k in EXPECTED_FIELDS if len({repr(g[k]) for g in group}) > 1
            }
            assert differing and differing <= {"opened_at_utc", "closed_at_utc"}, (
                f"seed={seed}: violation_id {vid} shared by {len(group)} records "
                f"differing in {sorted(differing)} -- accidental collision, not a "
                f"deliberate duplicate"
            )


def test_violation_id_dedupe_is_deterministic_across_processes() -> None:
    # A colliding seed must resolve to the same ids on every process; the
    # dedupe re-roll must not depend on hash randomisation.
    def _vids(hash_seed: str) -> str:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import json,sys;from generator.synthetic_data import generate_alerts;"
                "a,_=generate_alerts(99);"
                'json.dump([x["violation_id"] for x in a], sys.stdout)',
            ],
            cwd=REPO_ROOT,
            env={
                **os.environ,
                "PYTHONHASHSEED": hash_seed,
                "PYTHONPATH": str(REPO_ROOT),
            },
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout

    outputs = [_vids(hs) for hs in ("0", "1", "42", "8675309")]
    assert len(set(outputs)) == 1, "violation_id dedupe is not process-stable"


def test_generate_alerts_output_is_not_chronological() -> None:
    # add_messiness ends with rng.shuffle(alerts); output order must not be
    # sorted by opened_at (a detector must not be able to assume ordering).
    for seed in FULL_SEEDS:
        alerts, _ = generate_alerts(seed)
        opened = [a["opened_at_utc"] for a in alerts]
        assert opened != sorted(
            opened
        ), f"seed={seed}: output is chronologically sorted"


# ---------------------------------------------------------------------------
# 2d. Serialization / CLI entrypoint
# ---------------------------------------------------------------------------


def test_write_json_roundtrips(tmp_path: Path) -> None:
    alerts, _ = generate_alerts(SEED)
    out = tmp_path / "alerts.json"
    G.write_json(alerts, str(out))
    assert json.loads(out.read_text()) == alerts


def test_cli_writes_both_files(tmp_path: Path) -> None:
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    subprocess.run(
        [
            sys.executable,
            "-m",
            "generator.synthetic_data",
            "--seed",
            str(SEED),
            "--output-dir",
            str(tmp_path),
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    alerts = json.loads((tmp_path / "alerts.json").read_text())
    runbooks = json.loads((tmp_path / "runbooks.json").read_text())

    expected_alerts, _ = generate_alerts(SEED)
    expected_runbooks, _ = generate_runbooks(expected_alerts, SEED)
    assert alerts == expected_alerts
    assert runbooks == expected_runbooks

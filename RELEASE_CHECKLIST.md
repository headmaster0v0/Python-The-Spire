# Release Checklist

## Ship Definition

This repo is considered shippable when all of the following stay true at the same time:

- the CLI can play through a complete run flow from random-seed startup and Neow to victory without reopening old protocol work
- official runtime content is closed: `missing_in_runtime == 0`
- static runtime-vs-source mechanics drift is closed: `runtime_source_mismatches == 0`
- offline audit stays green without network access
- the Phase 267 fidelity gate stays green: non-card runtime surfaces are not empty shells, `known_approximations` is empty, dynamic truth aggregate tests stay green, and scripted CLI signoff stays green across all four characters
- repeated-run stability is a checked-in baseline for harness, audit, and stateful card identity lanes

This ship target is close source fidelity, not seed-perfect parity.

## Non-Goals

- not seed-perfect parity
- not new card/content expansion
- not recorder or harness schema changes
- not broad new `stslog` collection
- not a new CLI action/choice protocol beyond the current read-only info surface

## Post-Ship Maintenance Mode

After Phase 264 closeout, the default repo posture is post-ship maintenance rather than another feature tranche.

- official runtime content is already closed for the audited ship scope
- offline audit and regression sentinels are the baseline truth checks
- only concrete, reproducible regressions should open new work
- do not treat "there might be another corner case" as a reason to reopen broad content or parity threads
- Phase 268 is a verification throughput pass on top of this maintenance posture, not a new gameplay tranche
- the default next step after Phase 268 is targeted maintenance; do not open a default Phase 269
- a one-off local failure is not, by itself, a reason to reopen a new mainline thread; prefer reproducible, source-backed, or checked-in-sentinel regressions

## Required Verification Commands

Run these commands from the repo root:

```powershell
python -m pytest -q tests/test_phase267_fidelity_audit.py tests/test_phase267_dynamic_truth.py tests/test_phase267_cli_real_play_signoff.py tests/test_play_cli_rendering.py tests/test_playability_closure.py
python -m pytest -q tests/test_phase264_closeout_ship_checklist.py tests/test_phase263_final_rc_signoff.py tests/test_harness_smoke.py tests/test_wiki_audit.py tests/test_full_campaign_stability.py
python C:\Users\HP\.codex\skills\sts-regression-orchestrator\scripts\run_regressions.py --repo . --new-tests tests/test_phase264_closeout_ship_checklist.py --focus silent
python -m pytest -q tests
```

## Phase 267 Fidelity Gate

This repo should only be described as "aligned closely enough to the original to trust a real playthrough" when all three checked-in lanes are green at the same time:

- `wiki_audit` remains green for runtime closure and card static truth
- `tests/test_phase267_dynamic_truth.py` remains green for representative relic / potion / monster / event / shop behavior families
- `tests/test_phase267_cli_real_play_signoff.py` remains green for the four-character scripted CLI walk, with no placeholder or mojibake surface

`sts_py/data/known_approximations.json` must stay empty. Any newly discovered approximation should become a failing test or blocker instead of living as a silent TODO.

## Daily Maintenance Commands

For routine post-ship maintenance, start with the lighter default chain:

```powershell
python scripts/run_dev_checks.py
python scripts/run_dev_checks.py --profile fast
python -m pytest -q tests/test_phase267_fidelity_audit.py tests/test_phase267_dynamic_truth.py tests/test_phase267_cli_real_play_signoff.py
python -m pytest -q tests/test_phase264_closeout_ship_checklist.py tests/test_phase263_final_rc_signoff.py tests/test_wiki_audit.py tests/test_full_campaign_stability.py
```

`python scripts/run_dev_checks.py` is the quickest daily smoke bundle. It now defaults to `smoke`.

`python scripts/run_dev_checks.py --profile fast` is the wider local regression lane before escalating to harness.

When `--jobs` is omitted, `run_dev_checks.py` now uses a profile-aware default:

- `smoke`: `1`
- `fast`: `2`
- `harness` / `full`: `min(4, os.cpu_count() or 2)`

The explicit `python -m pytest ...phase263...` line remains the fuller checked-in maintenance chain when you also want the repeated-run signoff sentinel in the loop.

Only add harness and live-log coverage when the bug being investigated actually touches those lanes:

```powershell
python scripts/run_dev_checks.py --profile harness
python scripts/run_dev_checks.py --profile full --jobs 4
python -m pytest -q tests/test_harness_smoke.py
python C:\Users\HP\.codex\skills\sts-regression-orchestrator\scripts\run_regressions.py --repo . --new-tests <targeted_test_file> --focus silent
```

`tests/test_harness_smoke.py` is the dominant wall-clock cost in this repo. For everyday development, prefer `scripts/run_dev_checks.py` or the daily chain above before escalating to the harness lane.

Phase 268 keeps the fidelity gate unchanged while improving verification throughput. The local `.pytest_tmp/dev_checks_timings.json` timing cache is allowed to guide shard balancing, but it is not a checked-in truth artifact.

## Optional Local Prerequisites

These are optional local prerequisites for the full harness/live-log surface.

Some harness and live-log smoke tests depend on local recorder logs under `STS_LOG_DIR` or the default `~/sts_data_logs` directory.

- optional local corpus log: old checked corpora such as `primary`, `secondary`, `octonary`
- optional recent live log: recent local replay samples such as the latest Ironclad live/shop runs
- checked-in fixture required: repo-tracked fixtures such as `tests/fixtures/wiki_audit/sample_raw_snapshot.json`

## Interpreting Results

- `skip` means the optional local log corpus is unavailable on this machine; this is not a ship blocker by itself.
- `fail` means a checked-in truth lane regressed and blocks ship readiness until fixed.
- missing checked-in fixtures are failures, not skips.

## Targeted Regression Intake

Classify new issues before changing code:

- gameplay truth bug
- CLI/readability bug
- harness/audit regression
- optional-local-log gap

Only collect a new targeted log when the problem is still ambiguous after checking `decompiled_src`, the current checked-in tests, and the existing log corpus.

Repeated-run fixture drift, harness instability, or replay-order pollution should be treated as `harness/audit regression` work. Keep that follow-up narrow; do not use it as a reason to reopen gameplay/content expansion by default.

## Stable CLI Command Surface

The formal stable command set remains:

- `help`
- `map`
- `mapimg`
- `deck`
- `relics`
- `potions`
- `draw`
- `discard`
- `inspect <index>`
- `status`
- `intent`
- `exhaust`

These commands are sufficient for the shipped "complete playable CLI run" target, including random-seed startup, the Neow opening phase, and the required combat info surface. Do not expand the top-level command surface unless a concrete high-frequency usability bug justifies a narrow change.

## Final Truth Lanes To Preserve

- stateful card wire shapes: `GeneticAlgorithm#<misc>[+]`, `RitualDagger#<misc>[+]`, `SearingBlow+N`
- autoplay / replay / copy-chain correctness
- end-turn retain / no-discard / ethereal boundary correctness
- repeated harness fixture stability and repeated offline audit stability
- Chinese-first CLI closeout surface without reopening gameplay truth
- close source fidelity, not seed-perfect parity

# Release-readiness gate

## What this checks

This CLI reads the eleven release-evidence files and writes a machine-readable audit and a self-contained dashboard for the configured next release. It reports release readiness; it does not certify that a historical hotfix applies to the next candidate.

## Required evidence

Place these exact relative paths under one evidence root:

- `Configs/acceptance_test_output_v2.16.0.json`
- `Notes/triage_1121_gemma3_logits.md`
- `Adapters/acceptance_test_notes.md`
- `Adapters/adapter_authoring_checklist.md`
- `Adapters/weight_conversion_checklist.csv`
- `Configs/release_config.yaml`
- `Releases/release_checklist.md`
- `Releases/demo_sweep_results.csv`
- `Notes/issue_triage_queue.csv`
- `Releases/pr_merge_log.csv`
- `Releases/release_notes_v2.16.1_2026-06-27.md`

The audit records every required path and its SHA-256. Missing any one is an error.

## Run it

```bash
uv run python -m transformer_lens.tools.release_readiness \
  --evidence-root /path/to/release-evidence \
  --output-root .
```

This regenerates `release_readiness_audit.json`, `release_readiness_dashboard.html`, and `MAINTAINER_NOTES.md`.

## Read the result

`release.decision` is `READY` when no gate blocks release and `NOT_READY` when at least one gate is `missing`, `failed`, or `contradiction`.

| State | Meaning | Release effect |
| --- | --- | --- |
| `passed` | Candidate-specific evidence meets this gate. | Non-blocking |
| `historical_fix_recorded` | A prior issue is recorded as fixed in a prior release; this is context only, not candidate verification. | Non-blocking |
| `missing` | Required candidate evidence was not supplied. | Blocking |
| `failed` | Supplied evidence fails its threshold or requirement. | Blocking |
| `contradiction` | A summary says pass while another supplied source breaks the same threshold. | Blocking |

For Gemma-3, read the source-labelled v2.16.0 recorded result, #1121 triage result, v2.16.1 post-fix result, and configured threshold together. A historical post-fix result does not substitute for candidate evidence. A green historical demo sweep, including 14/14 through v2.16.0, does not establish the configured next release is ready: the candidate needs its own sweep.

## Before cutting

Resolve every blocker, rerun the CLI against the updated evidence root, and inspect:

1. `release_readiness_audit.json` for the decision, blockers, measurements, and provenance.
2. `release_readiness_dashboard.html` for reviewer-facing presentation.
3. The listed source files for any contradiction.

## Current limitations

- The CI gate cannot currently clear. `release_config.yaml` requires green CI, but none of the eleven inputs contains a candidate CI confirmation, so the CLI always reports that gate as `missing`. Add a defined candidate-CI evidence source and have the CLI evaluate it.
- The Gemma-3 contradiction is permanent by construction. The fixed inputs always pair the historical v2.16.0 passing record with #1121's threshold-breaking observation, so the CLI will continue to report `contradiction`. Add a named v2.17.0 candidate acceptance input and evaluate it separately, while retaining the historical incident as context.

## Verify the implementation

```bash
make format
uv run mypy transformer_lens/tools/release_readiness.py
uv run pytest tests/unit/tools/test_release_readiness.py -q
```

The tests cover a Gemma delta below `1e-4` passing, a delta above `1e-4` failing, a 6/6-style summary contradicted by threshold-breaking triage evidence, and historical green demo sweeps not being treated as evidence for the next release.

## Repository exception

This fork currently exposes main and gh-pages; it has no dev branch. Although the contributing guide normally directs pull requests to dev, this release-readiness work was created from main on the unmerged release-readiness-gate branch. No pull request has been opened against any branch.

# Maintainer release-readiness notes

## Decision

**v2.17.0 (2026-07-30): NOT_READY**

## Blocking evidence

- Demo sweeps are green 14/14 through v2.16.0; none proves v2.17.0 is ready because no v2.17.0 sweep is recorded.
- CI green is required, but no candidate CI confirmation is among the eleven inputs.
- v2.16.0 recorded 3.9e-05; triage 1.3e-04 exceeded 1.0e-04; v2.16.1 post-fix 2.9e-05.

## Interpretation

The v2.16.0 short-prompt result was 3.9e-5, triage found 1.3e-4 against the 1e-4 threshold, and the v2.16.1 post-fix result was 2.9e-5. An all-passed short-prompt summary is not a clean numerical pass when the recorded triage evidence exceeds the same threshold. Resolve that contradiction with a release-candidate Gemma-3 evidence bundle: fixed short and stress prompts, intermediate-activation deltas, checkpoint/dependency revisions, and the configured threshold.

## Repository exception

This fork has no dev branch; release-readiness-gate is based on main.

# Maintainer release-readiness notes

## Decision

**v2.17.0 (2026-07-30): do-not-cut**

## Blocking evidence

- No recorded Wednesday sweep for v2.17.0.
- CI green is required, but no candidate CI confirmation is among the eleven inputs.
- Recorded pass at 3.9e-05, but triage records 1.3e-04 over 1.0e-04.

## Interpretation

An all-passed short-prompt summary is not a clean numerical pass when the recorded triage evidence exceeds the same threshold. Resolve that contradiction with a release-candidate Gemma-3 evidence bundle: fixed short and stress prompts, intermediate-activation deltas, checkpoint/dependency revisions, and the configured threshold.

## Repository exception

This fork has no dev branch; release-readiness-gate is based on main.

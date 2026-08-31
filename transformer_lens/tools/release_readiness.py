"""Build a release-readiness audit from the maintained release evidence.

Usage:
    uv run python -m transformer_lens.tools.release_readiness \
        --evidence-root /path/to/release-evidence

The evidence root must preserve the eleven paths listed in ``REQUIRED_PATHS``.
Outputs are written to the current directory by default.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REQUIRED_PATHS = (
    "Configs/acceptance_test_output_v2.16.0.json",
    "Notes/triage_1121_gemma3_logits.md",
    "Adapters/acceptance_test_notes.md",
    "Adapters/adapter_authoring_checklist.md",
    "Adapters/weight_conversion_checklist.csv",
    "Configs/release_config.yaml",
    "Releases/release_checklist.md",
    "Releases/demo_sweep_results.csv",
    "Notes/issue_triage_queue.csv",
    "Releases/pr_merge_log.csv",
    "Releases/release_notes_v2.16.1_2026-06-27.md",
)
THRESHOLD = 1e-4
BRANCH_EXCEPTION = "This fork has no dev branch; release-readiness-gate is based on main."


@dataclass(frozen=True)
class Gate:
    name: str
    state: str
    evidence: str
    detail: str


def _read(root: Path, relative_path: str) -> str:
    return (root / relative_path).read_text(encoding="utf-8")


def _next_release(release_config: str) -> tuple[str, str]:
    match = re.search(
        r'next:\s*\{\s*version:\s*["\']?([^,"\'} ]+)["\']?,\s*date:\s*["\']?([^,"\'} ]+)',
        release_config,
    )
    if match is None:
        raise ValueError("release_config.yaml does not define next version and date")
    return match.group(1), match.group(2)


def _triage_max_delta(triage: str) -> float | None:
    match = re.search(r"~?([0-9]+(?:\.[0-9]+)?e-[0-9]+)\s+max absolute", triage, re.IGNORECASE)
    return float(match.group(1)) if match else None


def _gemma_result(acceptance: dict[str, Any]) -> dict[str, Any] | None:
    return next(
        (result for result in acceptance.get("results", []) if result.get("family") == "gemma-3"),
        None,
    )


def evaluate_gemma_acceptance(
    acceptance: dict[str, Any], triage: str, threshold: float = THRESHOLD
) -> Gate:
    """Assess the Gemma evidence, including post-release contradicting evidence."""
    gemma = _gemma_result(acceptance)
    if gemma is None:
        return Gate(
            "Gemma-3 numerical evidence", "missing", "acceptance output", "No Gemma-3 result"
        )

    recorded_delta = float(gemma["max_logit_delta"])
    triage_delta = _triage_max_delta(triage)
    recorded_pass = bool(gemma.get("pass")) and recorded_delta <= threshold

    if triage_delta is not None and triage_delta > threshold and recorded_pass:
        return Gate(
            "Gemma-3 numerical evidence",
            "contradiction",
            "Configs/acceptance_test_output_v2.16.0.json; Notes/triage_1121_gemma3_logits.md",
            f"Recorded pass at {recorded_delta:.1e}, but triage records {triage_delta:.1e} over {threshold:.1e}.",
        )
    if not recorded_pass or (triage_delta is not None and triage_delta > threshold):
        delta = max(recorded_delta, triage_delta or recorded_delta)
        return Gate(
            "Gemma-3 numerical evidence",
            "failed",
            "Configs/acceptance_test_output_v2.16.0.json; Notes/triage_1121_gemma3_logits.md",
            f"Maximum observed delta {delta:.1e} exceeds or fails threshold {threshold:.1e}.",
        )
    return Gate(
        "Gemma-3 numerical evidence",
        "passed",
        "Configs/acceptance_test_output_v2.16.0.json",
        f"Recorded maximum delta {recorded_delta:.1e} is within threshold {threshold:.1e}.",
    )


def _demo_gate(demo_sweep: str, version: str) -> Gate:
    rows = list(csv.DictReader(demo_sweep.splitlines()))
    row = next((candidate for candidate in rows if candidate.get("release") == version), None)
    if row is None:
        return Gate(
            "Demo notebook sweep",
            "missing",
            "Releases/demo_sweep_results.csv",
            f"No recorded Wednesday sweep for v{version}.",
        )
    state = "passed" if row.get("result") == "green" else "failed"
    return Gate(
        "Demo notebook sweep",
        state,
        "Releases/demo_sweep_results.csv",
        f"{row.get('notebooks_passed')}/{row.get('notebooks_run')} notebooks passed.",
    )


def _ci_gate(release_config: str) -> Gate:
    required = re.search(r"^\s*ci:\s*green", release_config, re.MULTILINE) is not None
    detail = "CI green is required, but no candidate CI confirmation is among the eleven inputs."
    return Gate(
        "CI and acceptance confirmation",
        "missing" if required else "not-configured",
        "Configs/release_config.yaml",
        detail,
    )


def _issue_gate(issue_queue: str) -> Gate:
    rows = list(csv.DictReader(issue_queue.splitlines()))
    gemma = next((row for row in rows if row.get("issue") == "1121"), None)
    open_bugs = [
        row["issue"]
        for row in rows
        if row.get("label") == "bug" and row.get("status") == "in-progress"
    ]
    if gemma is None or "v2.16.1" not in gemma.get("status", ""):
        return Gate(
            "Gemma-3 hotfix disposition",
            "failed",
            "Notes/issue_triage_queue.csv",
            "#1121 is not recorded as fixed.",
        )
    suffix = f" Open unrelated in-progress bugs: {', '.join(open_bugs)}." if open_bugs else ""
    return Gate(
        "Gemma-3 hotfix disposition",
        "passed",
        "Notes/issue_triage_queue.csv",
        "#1121 is closed in v2.16.1." + suffix,
    )


def audit(evidence_root: Path) -> dict[str, Any]:
    missing = [path for path in REQUIRED_PATHS if not (evidence_root / path).is_file()]
    if missing:
        raise FileNotFoundError("Missing required evidence: " + ", ".join(missing))

    evidence = {path: _read(evidence_root, path) for path in REQUIRED_PATHS}
    release_config = evidence["Configs/release_config.yaml"]
    acceptance = json.loads(evidence["Configs/acceptance_test_output_v2.16.0.json"])
    triage = evidence["Notes/triage_1121_gemma3_logits.md"]
    version, date = _next_release(release_config)
    gates = [
        _demo_gate(evidence["Releases/demo_sweep_results.csv"], version),
        _ci_gate(release_config),
        _issue_gate(evidence["Notes/issue_triage_queue.csv"]),
        evaluate_gemma_acceptance(acceptance, triage),
    ]
    blockers = [
        gate.detail for gate in gates if gate.state in {"missing", "failed", "contradiction"}
    ]
    gemma = _gemma_result(acceptance) or {}
    return {
        "release": {
            "version": version,
            "scheduled_date": date,
            "decision": "do-not-cut" if blockers else "ready-to-cut",
        },
        "gates": [asdict(gate) for gate in gates],
        "blockers": blockers,
        "measurements": {
            "acceptance_summary": acceptance.get("summary", {}),
            "threshold_abs_logit_delta": acceptance.get("threshold_abs_logit_delta", THRESHOLD),
            "gemma3_recorded_max_logit_delta": gemma.get("max_logit_delta"),
            "gemma3_triage_max_logit_delta": _triage_max_delta(triage),
        },
        "provenance": {
            "evidence_root": str(evidence_root),
            "paths": [
                {"path": path, "sha256": hashlib.sha256(text.encode()).hexdigest()}
                for path, text in evidence.items()
            ],
        },
        "repository_exception": BRANCH_EXCEPTION,
    }


def _dashboard(audit_data: dict[str, Any]) -> str:
    rows = "".join(
        '<tr><td>{}</td><td class="{}">{}</td><td>{}</td></tr>'.format(
            html.escape(gate["name"]),
            html.escape(gate["state"]),
            html.escape(gate["state"]),
            html.escape(gate["detail"]),
        )
        for gate in audit_data["gates"]
    )
    blockers = "".join(f"<li>{html.escape(blocker)}</li>" for blocker in audit_data["blockers"])
    release = audit_data["release"]
    return f"""<!doctype html>
<html lang=\"en\"><meta charset=\"utf-8\"><title>Release readiness</title>
<style>body{{font-family:system-ui,sans-serif;max-width:960px;margin:3rem auto;padding:0 1rem;color:#172033}}h1{{margin-bottom:.2rem}}.decision{{font-size:1.5rem;font-weight:700;color:#a33}}table{{border-collapse:collapse;width:100%;margin:1.5rem 0}}td,th{{border:1px solid #ccd3df;padding:.7rem;text-align:left}}.passed{{color:#16753a;font-weight:700}}.missing,.failed,.contradiction{{color:#af2638;font-weight:700}}code{{background:#eef2f7;padding:.15rem .3rem}}</style>
<h1>Release readiness: v{html.escape(release['version'])}</h1><p>Scheduled date: {html.escape(release['scheduled_date'])}</p>
<p class=\"decision\">Decision: {html.escape(release['decision'])}</p>
<table><thead><tr><th>Gate</th><th>State</th><th>Evidence</th></tr></thead><tbody>{rows}</tbody></table>
<h2>Blockers</h2><ul>{blockers}</ul><h2>Repository exception</h2><p>{html.escape(audit_data['repository_exception'])}</p>
<h2>Provenance</h2><p>All eleven supplied paths are recorded in <code>release_readiness_audit.json</code>.</p></html>"""


def _notes(audit_data: dict[str, Any]) -> str:
    release = audit_data["release"]
    blockers = "\n".join(f"- {blocker}" for blocker in audit_data["blockers"])
    return f"""# Maintainer release-readiness notes

## Decision

**v{release['version']} ({release['scheduled_date']}): {release['decision']}**

## Blocking evidence

{blockers}

## Interpretation

An all-passed short-prompt summary is not a clean numerical pass when the recorded triage evidence exceeds the same threshold. Resolve that contradiction with a release-candidate Gemma-3 evidence bundle: fixed short and stress prompts, intermediate-activation deltas, checkpoint/dependency revisions, and the configured threshold.

## Repository exception

{audit_data['repository_exception']}
"""


def write_outputs(audit_data: dict[str, Any], output_root: Path) -> None:
    (output_root / "release_readiness_audit.json").write_text(
        json.dumps(audit_data, indent=2) + "\n", encoding="utf-8"
    )
    (output_root / "release_readiness_dashboard.html").write_text(
        _dashboard(audit_data), encoding="utf-8"
    )
    (output_root / "MAINTAINER_NOTES.md").write_text(_notes(audit_data), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--evidence-root",
        type=Path,
        required=True,
        help="Directory containing the eleven evidence paths",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("."),
        help="Directory for generated release-readiness outputs",
    )
    args = parser.parse_args()
    audit_data = audit(args.evidence_root)
    write_outputs(audit_data, args.output_root)
    print(f"v{audit_data['release']['version']}: {audit_data['release']['decision']}")


if __name__ == "__main__":
    main()

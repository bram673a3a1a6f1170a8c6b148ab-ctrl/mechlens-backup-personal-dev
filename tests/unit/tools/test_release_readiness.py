from transformer_lens.tools.release_readiness import evaluate_gemma_acceptance


def _acceptance(delta: float, passed: bool = True) -> dict:
    return {"results": [{"family": "gemma-3", "max_logit_delta": delta, "pass": passed}]}


def test_gemma_delta_below_threshold_passes_gate():
    gate = evaluate_gemma_acceptance(_acceptance(9.9e-5), "No threshold-breaking observation.")
    assert gate.state == "passed"


def test_gemma_delta_above_threshold_fails_gate():
    gate = evaluate_gemma_acceptance(_acceptance(1.1e-4), "No threshold-breaking observation.")
    assert gate.state == "failed"


def test_all_passed_summary_with_triage_break_is_a_contradiction():
    acceptance = _acceptance(3.9e-5)
    acceptance["summary"] = {"total": 6, "passed": 6, "failed": 0}
    gate = evaluate_gemma_acceptance(
        acceptance,
        "A longer prompt reached ~1.3e-4 max absolute, over the acceptance threshold.",
    )
    assert gate.state == "contradiction"
    assert "1.3e-04" in gate.detail

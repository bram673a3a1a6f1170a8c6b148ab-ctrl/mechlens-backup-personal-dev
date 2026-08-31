from transformer_lens.tools.release_readiness import (
    _demo_gate,
    evaluate_gemma_acceptance,
)


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
        "A longer prompt reached ~1.3e-4 max absolute, over the acceptance threshold. "
        "Max delta back to 2.9e-5.",
    )
    assert gate.state == "contradiction"
    assert "1.3e-04" in gate.detail
    assert "2.9e-05" in gate.detail


def test_historical_demo_sweeps_do_not_prove_the_next_release_is_ready():
    gate = _demo_gate(
        "release,result,notebooks_run,notebooks_passed\n2.16.0,green,14,14\n", "2.17.0"
    )
    assert gate.state == "missing"
    assert "green 14/14 through v2.16.0" in gate.detail
    assert "none proves v2.17.0 is ready" in gate.detail

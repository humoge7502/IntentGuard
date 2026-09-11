"""AttackBench regression gate: detection must stay high, false positives low.
These thresholds are the project's security regression floor."""
from intentguard.attackbench.runner import run_benchmark

from tests.conftest import INTENT_TEXT  # noqa: F401


def test_attackbench_detection_and_false_positives(engine, org_ctx):
    report = run_benchmark(engine, org_ctx.org.org_id, max_per_family=6)

    assert report["total"] > 100
    assert report["attacks"] > 70
    assert report["benign"] > 10
    # security floor: at least 95% of attacks detected
    assert report["detection_rate"] >= 0.95, report["failures"][:5]
    # usability floor: at most 2% of benign scenarios wrongly stopped
    assert report["false_positive_rate"] <= 0.02, report["failures"][:5]
    # every family must achieve at least 80% pass rate
    for family, stats in report["per_family"].items():
        rate = stats["passed"] / stats["total"]
        assert rate >= 0.8, f"family {family} at {rate:.0%}: {stats}"

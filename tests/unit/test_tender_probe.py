from shared.contracts.enums import TenderReadinessStatus
from shared.domain.probes import TenderReadinessProbe
from shared.testing import case_tender_not_ready


def test_tender_probe_activates_and_returns_not_ready() -> None:
    profile = case_tender_not_ready()
    probe = TenderReadinessProbe()
    result = probe.evaluate(profile)

    assert probe.should_activate(profile)
    assert result.status == TenderReadinessStatus.NOT_READY
    assert "Weak financial capacity" in result.evidence

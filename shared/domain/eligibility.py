from __future__ import annotations

from shared.contracts.enums import EligibilityStatus
from shared.contracts.schemas import EligibilityResult, ProjectProfile, ResourceMatch


def evaluate_eligibility(profile: ProjectProfile, resources: list[ResourceMatch]) -> list[EligibilityResult]:
    return [_evaluate_one(profile, resource) for resource in resources]


def _evaluate_one(profile: ProjectProfile, resource: ResourceMatch) -> EligibilityResult:
    matched: list[str] = []
    failed: list[str] = []
    missing: list[str] = []

    if resource.country == profile.country:
        matched.append(f"Country = {profile.country}")
    else:
        failed.append(f"Country must be {resource.country}")

    if not resource.eligibility_conditions:
        missing.append("Documented eligibility conditions")

    for condition in resource.eligibility_conditions:
        field = condition.get("field")
        expected = condition.get("equals")
        min_value = condition.get("min")
        label = condition.get("label", field)
        actual = getattr(profile, str(field), None)
        if actual is None:
            missing.append(str(label))
            continue
        if expected is not None and actual != expected:
            failed.append(f"{label} expected {expected}")
        elif min_value is not None and float(actual) < float(min_value):
            failed.append(f"{label} must be at least {min_value}")
        else:
            matched.append(str(label))

    if failed:
        status = EligibilityStatus.NOT_ELIGIBLE
    elif missing:
        status = EligibilityStatus.POSSIBLY_ELIGIBLE if matched else EligibilityStatus.INSUFFICIENT_DATA
    else:
        status = EligibilityStatus.ELIGIBLE

    return EligibilityResult(
        resource_id=resource.resource_id,
        status=status,
        matched_conditions=matched,
        failed_conditions=failed,
        missing_conditions=missing,
    )

from __future__ import annotations

from typing import Any

from shared.contracts.enums import MaturityStage, Severity

STAGE_ORDER: dict[MaturityStage, int] = {
    MaturityStage.IDEATION: 0,
    MaturityStage.MARKET_VALIDATION: 1,
    MaturityStage.STRUCTURATION: 2,
    MaturityStage.FUNDRAISING: 3,
    MaturityStage.LAUNCH_PLANNING: 4,
    MaturityStage.GROWTH: 5,
}


SEVERITY_ORDER: dict[Severity, int] = {
    Severity.CRITICAL: 0,
    Severity.HIGH: 1,
    Severity.MEDIUM: 2,
    Severity.LOW: 3,
}


def clamp(value: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, value))


def stage(value: MaturityStage | str | None) -> MaturityStage:
    if value is None:
        return MaturityStage.IDEATION
    if isinstance(value, MaturityStage):
        return value
    return MaturityStage(value)


def present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list | dict | tuple | set):
        return bool(value)
    return True


def score_from_bool(value: bool | None, yes: float = 100, no: float = 20, missing: float = 45) -> float:
    if value is None:
        return missing
    return yes if value else no

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from pydantic import BaseModel

from shared.contracts.schemas import CompositeScores, ProjectProfile, Score, SubScore
from shared.domain.utils import clamp, score_from_bool
from shared.intake.requirements import criteria_evidence_factor

if TYPE_CHECKING:
    from collections.abc import Mapping

    from shared.intake.contracts import LedgerEntry
from shared.contracts.enums import EvidenceStatus

logger = logging.getLogger(__name__)
#: Default weakest-link penalty coefficient.
LAMBDA_DEFAULT: float = 0.5
 
#: A score below this threshold is considered "weak" by resource_service and roadmap_service
WEAK_SCORE_THRESHOLD: float = 55.0
 
#: Scoring model version
SCORING_VERSION: str = "weighted-rules-v0.1.0"

def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    """
    Clamp *value* to [lo, hi]. All composite outputs pass through this.
    """
    return max(lo, min(hi, value))
 
 
def _trl_to_score(trl: int | None) -> float | None:
    """
    Convert a TRL integer (1–9) to a 0–100 sub-score using the
    TRL/IRL ladder from Image 1.
 
    Rationale: a single float TRL field is arbitrary; this ladder
    produces a defensible, judge-legible rubric tied to EU/NASA standard
    technology readiness levels.
 
    TRL 1-3  →  0–20   (basic concept; 100% RTD risk)
    TRL 4    →  21–35  (lab-validated; >97% risk)
    TRL 5-6  →  36–55  (pilot / IRL revenue-model validation; >90% risk)
    TRL 7    →  56–75  (prototype operational; RTD risk break-even)
    TRL 8    →  76–90  (field demo; industrially validated)
    TRL 9    →  91–100 (full-scale commercial deployment)
    """
    if trl is None:
        return None
    mapping = {1: 5, 2: 10, 3: 20, 4: 30, 5: 40, 6: 55, 7: 70, 8: 83, 9: 95}
    return float(mapping.get(trl, 0))
 
 
def _ledger_evidence(
    profile: ProjectProfile,
    field_name: str,
) -> EvidenceStatus | None:
    """
    Return the EvidenceStatus for *field_name* from the evidence_ledger,
    or None if the field has never been tagged by the intake engine.
    """
    entry = profile.evidence_ledger.get(field_name)
    return entry.status if entry else None
 
 
def _evidence_factor(
    profile: ProjectProfile,
    field_name: str,
) -> float:
    """
    Return e_j in {0.0, 1.0} for the confidence formula.

    CONFIRMED ledger evidence counts as 1. Explicit UNVERIFIED,
    CONTRADICTED, or MISSING ledger evidence counts as 0. When no intake
    ledger exists, a present profile value is considered usable for the
    local deterministic MVP path, while absent values keep confidence low.
    """
    status = _ledger_evidence(profile, field_name)
    if status is not None:
        return 1.0 if status == EvidenceStatus.CONFIRMED else 0.0
    value = _field_value(profile, field_name)
    if value is None or value == "" or value == []:
        return 0.0
    return 1.0
def _field_value(profile: ProjectProfile, field_name: str) -> Any:
    """Safe attribute access on ProjectProfile with a None fallback."""
    return getattr(profile, field_name, None)
 
 
# Core sub-criterion descriptor
# ---------------------------------------------------------------------------
 
@dataclass
class CriterionSpec:
    """
    Describes one sub-criterion within a scoring dimension.
 
    Attributes
    ----------
    name:
        Human-readable label shown in the dashboard sub-score breakdown.
    field:
        The ProjectProfile attribute that provides the raw value (0–100 int
        or 0–1 float). If a custom *extractor* is supplied, this field is
        used only for the evidence_ledger lookup.
    weight:
        Contribution weight wⱼ. All weights in one dimension must sum to 1.0.
    fundamental:
        If True, this criterion is eligible for the λ-penalty. A score of 0
        on any fundamental criterion will penalise the composite by up to
        λ × 100% regardless of other criteria strengths.
    extractor:
        Optional callable (profile → float | None) for fields that need
        transformation (e.g. TRL ladder, boolean → 0/100, list length).
    rule_id:
        Short identifier included in Score.triggered_rules[] so the audit
        trail can reference which rule produced the sub-score.
    """
    name: str
    field: str
    weight: float
    fundamental: bool = False
    extractor: Any = None   # Callable[[ProjectProfile], float | None] | None
    rule_id: str = ""
 
 
# ---------------------------------------------------------------------------
# Anomaly rule descriptor
# ---------------------------------------------------------------------------
 
@dataclass
class AnomalyRule:
    """
    A contradiction check run after sub-scores are computed.
 
    The check() callable receives the ProjectProfile and the dict of
    sub-score raw values {criterion_name: raw_value_0_to_1}.
    It returns True when the anomaly condition is met.
 
    When triggered, the anomaly_id is appended to Score.anomalies[] and
    the evidence factor for all *penalised_fields* is forced to 0 — this
    degrades confidence to signal the inconsistency.
 
    See §2.4.3 of the spec. The spec requires ≥2 demonstrated cases.
    """
    anomaly_id: str
    description: str
    penalised_fields: list[str] = field(default_factory=list)
    check: Any = None   # Callable[[ProjectProfile, dict[str, float]], bool]
 
 # Weakest-link composite calculator
# ---------------------------------------------------------------------------
 
def _compute_composite(
    raw_values: dict[str, float],          # {criterion_name: 0–1 float}
    criteria: list[CriterionSpec],
    lambda_penalty: float = LAMBDA_DEFAULT,
) -> tuple[float, list[SubScore], list[str]]:
    """
    Implement the two-step scoring formula from the spec §5.
 
    Returns
    -------
    composite_0_to_100:
        Final composite score after λ-penalty, scaled to 0–100.
    sub_scores:
        List of SubScore objects for dashboard breakdown rendering.
    missing_criteria:
        Names of criteria where raw_values was None (no evidence at all).
    """
    # ── Step 1: weighted base ──────────────────────────────────────────────
    c_base: float = 0.0
    sub_scores: list[SubScore] = []
    missing_criteria: list[str] = []
 
    # Track the lowest-scoring fundamental criterion for the λ-penalty.
    # Initialise to 1.0 (no penalty if no fundamental has low score).
    x_min_fundamental: float = 1.0
 
    for spec in criteria:
        raw = raw_values.get(spec.name)
 
        if raw is None:
            # No evidence — record as missing, contribute 0 to base.
            missing_criteria.append(spec.name)
            raw_norm = 0.0
        else:
            # Normalise raw value to [0,1] regardless of whether the
            # field was stored as 0–100 int or 0–1 float.
            raw_norm = raw / 100.0 if raw > 1.0 else raw
 
        contribution = spec.weight * raw_norm
        c_base += contribution
 
        sub_scores.append(SubScore(
            name=spec.name,
            value=_clamp(raw_norm * 100.0),
            weight=spec.weight,
            contribution=_clamp(contribution * 100.0),
            fundamental=spec.fundamental,
        ))
 
        if spec.fundamental and raw is not None:
            x_min_fundamental = min(x_min_fundamental, raw_norm)
 
    # ── Step 2: weakest-link λ-penalty ────────────────────────────────────
    # C = C_base × (1 − λ × (1 − x*_min))
    #
    # If x*_min == 1.0 (no fundamental weakness) the multiplier is 1.0
    # and C == C_base — no penalty.
    #
    # If x*_min == 0.0 and λ == 0.5, the composite is halved regardless
    # of how strong the remaining sub-criteria are.
    penalty_multiplier = 1.0 - lambda_penalty * (1.0 - x_min_fundamental)
    composite_norm = c_base * penalty_multiplier
    composite = _clamp(composite_norm * 100.0)
 
    logger.debug(
        "composite: C_base=%.3f λ=%.2f x*_min=%.3f multiplier=%.3f → C=%.1f",
        c_base, lambda_penalty, x_min_fundamental, penalty_multiplier, composite,
    )
 
    return composite, sub_scores, missing_criteria
 
 
def _compute_confidence(
    profile: ProjectProfile,
    criteria: list[CriterionSpec],
    anomaly_penalised_fields: set[str],
) -> float:
    """
    Implement the weight-aware confidence formula
  
    eⱼ = 1 iff evidence_ledger[field] == CONFIRMED
    eⱼ = 0 for UNVERIFIED, CONTRADICTED, absent, or anomaly-penalised.
 
    This means missing a 0.40-weight fundamental hurts confidence far more
    than missing a 0.10-weight minor criterion
    """
    confidence: float = 0.0
    for spec in criteria:
        # Force eⱼ = 0 if this field is involved in a triggered anomaly.
        if spec.field in anomaly_penalised_fields:
            e_j = 0.0
        else:
            e_j = _evidence_factor(profile, spec.field)
        confidence += spec.weight * e_j
    return _clamp(confidence, 0.0, 1.0)
 
# Raw value extractors (one per scoring dimension)
# ---------------------------------------------------------------------------
# Each extractor maps a ProjectProfile to a dict {criterion_name: raw_value}
# where raw_value ∈ [0,100] or [0,1] (both are normalised in _compute_composite).
# None means "no data at all" → recorded as missing.
 
def _extract_market(profile: ProjectProfile) -> dict[str, float | None]:
    """
    Market Score raw values.
 
    Fundamental criteria (eligible for λ-penalty):
      - Market-share potential  (market_size_known → binary)
      - Customer validation     (paying_customers scaled, capped at 100)
 
    Non-fundamental:
      - Revenue-model clarity   (revenue_model_clarity 0–100)
      - Competitive differentiation (competition_understanding 0–100)
    """
    paying = profile.paying_customers
    # Scale: 0 customers → 0, 10+ customers → 100 (linear, capped)
    customer_score: float | None = None
    if paying is not None:
        customer_score = min(paying * 10.0, 100.0)
 
    return {
        "Market-share potential": 100.0 if profile.market_size_known else (0.0 if profile.market_size_known is False else None),
        "Customer validation": customer_score,
        "Revenue-model clarity": float(profile.revenue_model_clarity) if profile.revenue_model_clarity is not None else None,
        "Competitive differentiation": float(profile.competition_understanding) if profile.competition_understanding is not None else None,
    }
 
 
def _extract_scalability(profile: ProjectProfile) -> dict[str, float | None]:
    """
    Scalability Score raw values.
 
    Fundamental criteria:
      - Process automation level  (0–1 float → converted to 0–100)
      - Tech stack scalability    (0–100 int)
 
    Non-fundamental:
      - Team capacity to scale    (team_size as proxy: 1→20, capped at 100)
      - Infrastructure readiness  (0–100 int)
    """
    auto = profile.process_automation_level
    auto_score: float | None = auto * 100.0 if auto is not None else None
 
    team = profile.team_size
    team_score: float | None = None
    if team is not None:
        # 1 person → 10, 10+ people → 100 (linear, capped)
        team_score = min(team * 10.0, 100.0)
 
    return {
        "Process automation level": auto_score,
        "Tech stack scalability": float(profile.tech_stack_scalability) if profile.tech_stack_scalability is not None else None,
        "Team capacity to scale": team_score,
        "Infrastructure readiness": float(profile.infrastructure_readiness) if profile.infrastructure_readiness is not None else None,
    }
 
 
def _extract_innovation(profile: ProjectProfile) -> dict[str, float | None]:
    """
    Innovation Score raw values.
 
    TRL ladder (Image 1): technology_readiness_level (1–9) is converted to
    a 0–100 sub-score via _trl_to_score() rather than used as a raw integer.
    This produces a defensible, judge-legible rubric aligned with EU/NASA TRL.
 
    Fundamental criteria:
      - Technological intensity (TRL ladder)
      - Problem novelty         (0–100 int)
 
    Non-fundamental:
      - IP / moat strength      (ip_assets list → binary presence)
      - R&D investment ratio    (0–1 float → 0–100)
    """
    trl_score = _trl_to_score(profile.technology_readiness_level)
 
    ip_score: float | None = None
    if profile.ip_assets is not None:
        ip_score = 80.0 if len(profile.ip_assets) > 0 else 10.0
 
    rd = profile.rd_investment_ratio
    rd_score: float | None = rd * 100.0 if rd is not None else None
 
    return {
        "Technological intensity (TRL)": trl_score,
        "Problem novelty": float(profile.problem_novelty_score) if profile.problem_novelty_score is not None else None,
        "IP / moat strength": ip_score,
        "R&D investment ratio": rd_score,
    }
 
 
def _extract_operational(profile: ProjectProfile) -> dict[str, float | None]:
    """
    Operational Score raw values.
 
    Fundamental criteria:
      - MVP / product artifact  (has_mvp → binary)
 
    Non-fundamental:
      - Process documentation   (0–100 int)
      - Financial model quality (0–100 int)
      - Legal / regulatory compliance (0–100 int)
    """
    mvp_score: float | None = None
    if profile.has_mvp is not None:
        mvp_score = 100.0 if profile.has_mvp else 0.0
 
    return {
        "MVP / product artifact": mvp_score,
        "Process documentation": float(profile.process_documentation_score) if profile.process_documentation_score is not None else None,
        "Financial model quality": float(profile.financial_model_quality) if profile.financial_model_quality is not None else None,
        "Legal / regulatory compliance": float(profile.legal_compliance_score) if profile.legal_compliance_score is not None else None,
    }
 
 
def _extract_green(profile: ProjectProfile) -> dict[str, float | None]:
    """
    Green Score raw values — mapped from Image 2's 4 environmental pillars.
 
    Pilier 1 Climat / Air     → climate_air_impact_score   (0–100)
    Pilier 2 Eau              → water_impact_score          (0–100)
    Pilier 3 Sols & biodiversité → soil_biodiversity_score  (0–100)
    Pilier 4 Ressources & déchets → resources_waste_score   (0–100)
    + SDG alignment           → sdg_alignment_score         (0–100)
      (This is the direct PNUD/UN link — the one place where external
       PNUD/UN framework is the explicit scoring rubric source.)
 
    NOTE: All five criteria are non-fundamental because environmental
    impact is additive, not gated — a founder with zero water usage is
    not penalised for fields that don't apply to their sector.
    The overall green_practices list is kept as a fallback signal but
    the four pillar scores are the primary evidence fields.
    """
    def _pillar(val: int | None) -> float | None:
        if val is None:
            return None
        return float(val)
 
    return {
        "Climat / Air impact": _pillar(profile.climate_air_impact_score),
        "Water impact": _pillar(profile.water_impact_score),
        "Soil & biodiversity": _pillar(profile.soil_biodiversity_score),
        "Resources & waste management": _pillar(profile.resources_waste_score),
        "SDG alignment (PNUD/UN)": _pillar(profile.sdg_alignment_score),
    }
 
 # Dimension specifications
# ---------------------------------------------------------------------------
# Weights must sum to 1.0 per dimension. Verified via assertion at import.
 
_MARKET_CRITERIA: list[CriterionSpec] = [
    CriterionSpec("Market-share potential",      "market_size_known",            weight=0.30, fundamental=True,  rule_id="MKT-01"),
    CriterionSpec("Customer validation",          "paying_customers",              weight=0.30, fundamental=True,  rule_id="MKT-02"),
    CriterionSpec("Revenue-model clarity",        "revenue_model_clarity",         weight=0.20, fundamental=False, rule_id="MKT-03"),
    CriterionSpec("Competitive differentiation",  "competition_understanding",      weight=0.20, fundamental=False, rule_id="MKT-04"),
]
 
_SCALABILITY_CRITERIA: list[CriterionSpec] = [
    CriterionSpec("Process automation level",    "process_automation_level",       weight=0.35, fundamental=True,  rule_id="SCL-01"),
    CriterionSpec("Tech stack scalability",       "tech_stack_scalability",         weight=0.30, fundamental=True,  rule_id="SCL-02"),
    CriterionSpec("Team capacity to scale",       "team_size",                      weight=0.20, fundamental=False, rule_id="SCL-03"),
    CriterionSpec("Infrastructure readiness",     "infrastructure_readiness",       weight=0.15, fundamental=False, rule_id="SCL-04"),
]
 
_INNOVATION_CRITERIA: list[CriterionSpec] = [
    CriterionSpec("Technological intensity (TRL)", "technology_readiness_level",   weight=0.35, fundamental=True,  rule_id="INN-01"),
    CriterionSpec("Problem novelty",               "problem_novelty_score",         weight=0.25, fundamental=True,  rule_id="INN-02"),
    CriterionSpec("IP / moat strength",            "ip_assets",                    weight=0.25, fundamental=False, rule_id="INN-03"),
    CriterionSpec("R&D investment ratio",          "rd_investment_ratio",           weight=0.15, fundamental=False, rule_id="INN-04"),
]
 
_OPERATIONAL_CRITERIA: list[CriterionSpec] = [
    CriterionSpec("MVP / product artifact",       "has_mvp",                       weight=0.35, fundamental=True,  rule_id="OPS-01"),
    CriterionSpec("Process documentation",        "process_documentation_score",   weight=0.25, fundamental=False, rule_id="OPS-02"),
    CriterionSpec("Financial model quality",      "financial_model_quality",       weight=0.25, fundamental=False, rule_id="OPS-03"),
    CriterionSpec("Legal / regulatory compliance","legal_compliance_score",        weight=0.15, fundamental=False, rule_id="OPS-04"),
]
 
_GREEN_CRITERIA: list[CriterionSpec] = [
    CriterionSpec("Climat / Air impact",          "climate_air_impact_score",      weight=0.30, fundamental=False, rule_id="GRN-01"),
    CriterionSpec("Water impact",                 "water_impact_score",            weight=0.25, fundamental=False, rule_id="GRN-02"),
    CriterionSpec("Soil & biodiversity",          "soil_biodiversity_score",       weight=0.20, fundamental=False, rule_id="GRN-03"),
    CriterionSpec("Resources & waste management", "resources_waste_score",         weight=0.15, fundamental=False, rule_id="GRN-04"),
    CriterionSpec("SDG alignment (PNUD/UN)",      "sdg_alignment_score",           weight=0.10, fundamental=False, rule_id="GRN-05"),
]
 
# Guard: catch weight drift at import time so tests fail loudly, not silently.
for _dim_name, _crit_list in [
    ("market", _MARKET_CRITERIA),
    ("scalability", _SCALABILITY_CRITERIA),
    ("innovation", _INNOVATION_CRITERIA),
    ("operational", _OPERATIONAL_CRITERIA),
    ("green", _GREEN_CRITERIA),
]:
    _total = round(sum(c.weight for c in _crit_list), 10)
    assert _total == 1.0, (
        f"Weights for {_dim_name} dimension sum to {_total}, expected 1.0. "
        "Fix CriterionSpec weights before proceeding."
    )
 
 
# ---------------------------------------------------------------------------
# Anomaly rules (spec §2.4.3 — requires ≥2 demonstrated cases)
# ---------------------------------------------------------------------------
 
def _anomaly_high_traction_no_evidence(
    profile: ProjectProfile,
    _raw: dict[str, float],
) -> bool:
    """
    ANOMALY: high_traction_no_documented_evidence  (Market Score)
 
    Condition: paying_customers >= 5 AND market_validation_evidence is empty.
 
    A founder claiming meaningful traction with zero documented validation
    evidence is internally contradicted. This violates the spec's core
    principle that stages are defined by verifiable ARTIFACTS, not declared
    intentions.
    """
    return (
        profile.paying_customers is not None
        and profile.paying_customers >= 5
        and len(profile.market_validation_evidence) == 0
    )
 
 
def _anomaly_manual_processes_limit_growth(
    profile: ProjectProfile,
    _raw: dict[str, float],
) -> bool:
    """
    ANOMALY: manual_processes_limit_growth  (Scalability Score)
 
    Condition: process_automation_level < 0.45 AND effective_stage == GROWTH.
 
    A growth-stage business operating with heavily manual processes signals
    a structural scalability ceiling inconsistent with the effective stage.
    """
    from shared.contracts.enums import MaturityStage
    from shared.domain.utils import stage

    return (
        profile.process_automation_level is not None
        and profile.process_automation_level < 0.45
        and stage(profile.declared_stage) == MaturityStage.GROWTH
    )
 
 
def _anomaly_high_innovation_no_ip(
    profile: ProjectProfile,
    _raw: dict[str, float],
) -> bool:
    """
    ANOMALY: high_innovation_claim_no_ip  (Innovation Score)
 
    Condition: problem_novelty_score > 80 AND ip_assets is empty.
 
    A high novelty claim with zero IP protection is an internal contradiction:
    if the innovation is genuinely novel, the absence of any IP filing
    suggests either the claim is unsubstantiated or the asset is unprotected.
    """
    return (
        profile.problem_novelty_score is not None
        and profile.problem_novelty_score > 80
        and len(profile.ip_assets) == 0
    )
 
 
def _anomaly_revenue_without_mvp(
    profile: ProjectProfile,
    _raw: dict[str, float],
) -> bool:
    """
    ANOMALY: revenue_without_mvp_artifact  (Operational Score)
 
    Condition: paying_customers > 0 AND has_mvp is False.
 
    Revenue reported without a verifiable MVP artifact directly violates
    MASSAR's artifact-first principle: stages are gated by confirmed
    artifacts, not declared numbers. This combination is logically
    impossible or fraudulent and must be flagged.
    """
    return (
        profile.paying_customers is not None
        and profile.paying_customers > 0
        and profile.has_mvp is False
    )
 
def _anomaly_high_sdg_without_practices(profile: ProjectProfile, _raw: dict[str, float]) -> bool:
    return (
        profile.sdg_alignment_score is not None
        and profile.sdg_alignment_score >= 80
        and len(profile.green_practices) == 0
    )
 
# Registry: {dimension_name: list[AnomalyRule]}
_ANOMALY_REGISTRY: dict[str, list[AnomalyRule]] = {
    "Market Score": [
        AnomalyRule(
            anomaly_id="high_traction_no_documented_evidence",
            description=(
                "paying_customers ≥ 5 but market_validation_evidence is empty — "
                "traction claim is not backed by any verifiable artifact."
            ),
            penalised_fields=["paying_customers", "market_validation_evidence"],
            check=_anomaly_high_traction_no_evidence,
        ),
    ],
    "Scalability Score": [
        AnomalyRule(
            anomaly_id="manual_processes_limit_growth",
            description=(
                "process_automation_level < 0.45 at GROWTH stage — "
                "manual operations cap scalability below growth-stage requirements."
            ),
            penalised_fields=["process_automation_level"],
            check=_anomaly_manual_processes_limit_growth,
        ),
    ],
    "Innovation Score": [
        AnomalyRule(
            anomaly_id="high_innovation_claim_no_ip",
            description=(
                "problem_novelty_score > 80 but ip_assets is empty — "
                "novelty claim unprotected and unsubstantiated."
            ),
            penalised_fields=["problem_novelty_score", "ip_assets"],
            check=_anomaly_high_innovation_no_ip,
        ),
    ],
    "Operational Score": [
        AnomalyRule(
            anomaly_id="revenue_without_mvp_artifact",
            description=(
                "paying_customers > 0 but has_mvp is False — "
                "revenue without a verifiable product artifact violates artifact-first principle."
            ),
            penalised_fields=["paying_customers", "has_mvp"],
            check=_anomaly_revenue_without_mvp,
        ),
    ],
    "Green Score": [
        AnomalyRule(
            anomaly_id="high_sdg_without_practices",
            description=(
                "sdg_alignment_score ≥ 80 but green_practices is empty — "
                "high SDG alignment claim without any documented environmental practices."
            ),
            penalised_fields=["sdg_alignment_score", "green_practices"],
            check=_anomaly_high_sdg_without_practices,
        ),
    ], 
}
 
 
# Highest-leverage action strings
# The spec mandates one actionable improvement string per score.
# These are selected based on which sub-criterion is weakest.
 
def _market_action(sub_scores: list[SubScore], composite: float) -> str:
    worst = min(sub_scores, key=lambda s: s.value)
    if worst.name == "Market-share potential":
        return "Commission a TAM/SAM/SOM analysis using APII sector data to establish a credible market-size figure."
    if worst.name == "Customer validation":
        return "Conduct 10 structured customer interviews (document willingness-to-pay) before the next scoring cycle."
    if worst.name == "Revenue-model clarity":
        return "Formalise the revenue model with unit economics (CAC, LTV, payback period) and attach it as an artifact."
    return "Map 3 direct competitors and document your differentiation in a one-page competitive landscape."
 
 
def _scalability_action(sub_scores: list[SubScore], composite: float) -> str:
    worst = min(sub_scores, key=lambda s: s.value)
    if worst.name == "Process automation level":
        return "Identify and automate the 3 most manual operational bottlenecks; target process_automation_level ≥ 0.60."
    if worst.name == "Tech stack scalability":
        return "Document current tech-stack capacity ceiling and produce a horizontal-scaling roadmap for 10× load."
    if worst.name == "Team capacity to scale":
        return "Define a 6-month hiring plan aligned with the projected growth curve; attach as a signed artifact."
    return "Benchmark infrastructure against a 10× traffic spike and document failover strategy."
 
 
def _innovation_action(sub_scores: list[SubScore], composite: float) -> str:
    worst = min(sub_scores, key=lambda s: s.value)
    if worst.name == "Technological intensity (TRL)":
        return "Produce a TRL 4 lab-validation report (documented test results) to move past the RTD risk break-even point."
    if worst.name == "Problem novelty":
        return "Conduct a prior-art search and document 3 ways your approach differs from existing alternatives."
    if worst.name == "IP / moat strength":
        return "File a provisional patent or trade-secret declaration before the next submission deadline."
    return "Increase R&D investment ratio to ≥ 10% of monthly budget and document expenditure."
 
 
def _operational_action(sub_scores: list[SubScore], composite: float) -> str:
    worst = min(sub_scores, key=lambda s: s.value)
    if worst.name == "MVP / product artifact":
        return "Ship an MVP that generates at least one paying transaction and upload the evidence artifact."
    if worst.name == "Process documentation":
        return "Document all core operational processes, assign owners, and version-control the documentation."
    if worst.name == "Financial model quality":
        return "Build an 18-month financial model with revenue, cost, and runway projections; attach as a spreadsheet."
    return "Complete legal compliance checklist (RNE registration, CNSS, DGI) and upload the certificates."
 
 
def _green_action(sub_scores: list[SubScore], composite: float) -> str:
    worst = min(sub_scores, key=lambda s: s.value)
    if worst.name == "Climat / Air impact":
        return "Baseline energy consumption (electricity, fuel, transport) and set a 20% reduction target aligned with SDG 13."
    if worst.name == "Water impact":
        return "Document water volume and rejection treatment; target zero untreated discharge per SDG 6."
    if worst.name == "Soil & biodiversity":
        return "Conduct an ecological sensitivity assessment of your operating site and document mitigation measures."
    if worst.name == "Resources & waste management":
        return "Implement a waste audit: quantify materials, recycling rate, and disposal modes per SDG 12."
    return "Map your activities to at least 3 UN Sustainable Development Goals and publish an SDG alignment statement."
 
 
# Per-dimension score builders
 
def _build_score(
    name: str,
    profile: ProjectProfile,
    criteria: list[CriterionSpec],
    raw_extractor: Any,                         # Callable[[ProjectProfile], dict]
    action_fn: Any,                              # Callable[[list[SubScore], float], str]
    anomaly_rules: list[AnomalyRule],
    lambda_penalty: float = LAMBDA_DEFAULT,
) -> Score:
    """
    Build one Score object for a given dimension.
 
    Steps:
      1. Extract raw values from the profile.
      2. Run anomaly checks; collect triggered IDs and penalised fields.
      3. Compute composite via _compute_composite() (λ-penalty formula).
      4. Compute confidence via _compute_confidence() (Σwⱼeⱼ).
      5. Select highest_leverage_action from the worst sub-criterion.
      6. Collect triggered rule IDs for the audit trail.
    """
    raw_values: dict[str, float | None] = raw_extractor(profile)
 
    # ── Step 2: anomaly detection ──────────────────────────────────────────
    triggered_anomalies: list[str] = []
    anomaly_penalised_fields: set[str] = set()
 
    for rule in anomaly_rules:
        try:
            if rule.check(profile, raw_values):
                triggered_anomalies.append(rule.anomaly_id)
                anomaly_penalised_fields.update(rule.penalised_fields)
                logger.info(
                    "Anomaly '%s' triggered for project %s: %s",
                    rule.anomaly_id, profile.project_id, rule.description,
                )
        except Exception as exc:  # noqa: BLE001
            # Anomaly check failure must never crash scoring.
            logger.warning("Anomaly rule '%s' raised: %s", rule.anomaly_id, exc)
 
    # ── Steps 3 & 4: compute composite and sub-scores ─────────────────────
    composite, sub_scores, missing_criteria = _compute_composite(
        raw_values={k: v for k, v in raw_values.items() if v is not None},
        criteria=criteria,
        lambda_penalty=lambda_penalty,
    )
 
    confidence = _compute_confidence(
        profile=profile,
        criteria=criteria,
        anomaly_penalised_fields=anomaly_penalised_fields,
    )
 
    # ── Step 5: select action ──────────────────────────────────────────────
    action = action_fn(sub_scores, composite)
 
    # ── Step 6: triggered rule IDs ────────────────────────────────────────
    triggered_rules = [
        spec.rule_id
        for spec in criteria
        if raw_values.get(spec.name) is not None and spec.rule_id
    ]
 
    return Score(
        name=name,
        value=composite,
        confidence=confidence,
        sub_scores=sub_scores,
        missing_criteria=missing_criteria,
        anomalies=triggered_anomalies,
        highest_leverage_action=action,
        triggered_rules=triggered_rules,
        version=SCORING_VERSION,
    )
 
 
# WeightedRuleScoreCalculator
 
class WeightedRuleScoreCalculator:
    """
    Main entry point for the MASSAR scoring service.
 
    Usage
    -----
    >>> calculator = WeightedRuleScoreCalculator()
    >>> scores: CompositeScores = calculator.compute(profile)
 
    The resulting CompositeScores object is consumed by:
      - resource_service  (weak_scores = {s.name for s in scores.scores if s.value < 55})
      - roadmap_service   (highest_leverage_action → RoadmapAction.rationale)
      - blocker_service   (TODO: wire scalability_score.value < 45 → SCALABILITY_BLOCKER)
 
    Parameters
    ----------
    lambda_penalty:
        Weakest-link penalty coefficient λ ∈ [0, 1].
        0.0 → plain weighted average (no penalty, violates spec).
        0.5 → default (spec-mandated).
        1.0 → zero-fundamental = zero-composite (maximum penalty).
    """
 
    def __init__(self, lambda_penalty: float = LAMBDA_DEFAULT) -> None:
        if not 0.0 <= lambda_penalty <= 1.0:
            raise ValueError(f"lambda_penalty must be in [0,1], got {lambda_penalty}")
        self.lambda_penalty = lambda_penalty
 
    def calculate(self, profile: ProjectProfile) -> CompositeScores:
        return self.compute(profile)

    def calculate_with_ledger(
        self,
        profile: ProjectProfile,
        ledger: Mapping[str, LedgerEntry],
    ) -> CompositeScores:
        score_to_criterion = {
            "Market Score": "market",
            "market_score": "market",
            "Operational Score": "commercial_offer",
            "operational_score": "commercial_offer",
            "Commercial Offer Score": "commercial_offer",
            "commercial_offer_score": "commercial_offer",
            "Innovation Score": "innovation",
            "innovation_score": "innovation",
            "Scalability Score": "scalability",
            "scalability_score": "scalability",
            "Green Score": "green",
            "green_score": "green",
        }
        scores = self.compute(profile)
        adjusted: list[Score] = []
        for score in scores.scores:
            factor = criteria_evidence_factor(ledger, score_to_criterion.get(score.name, score.name))
            adjusted.append(score.model_copy(update={"confidence": round(score.confidence * factor, 3)}))
        return CompositeScores(scores=adjusted, version=scores.version)
    def compute(self, profile: ProjectProfile) -> CompositeScores:
        """
        Compute all five dimension scores and return a CompositeScores object.
 
        This is the only public method. All five scores are computed
        independently; a failure in one dimension does not block the others.
 
        Returns
        -------
        CompositeScores
            .scores — list of 5 Score objects
            .version — scoring model version string
        """
        scores: list[Score] = []
 
        dimensions = [
            ("Market Score",      _MARKET_CRITERIA,       _extract_market,      _market_action,      _ANOMALY_REGISTRY["Market Score"]),
            ("Scalability Score", _SCALABILITY_CRITERIA,  _extract_scalability, _scalability_action, _ANOMALY_REGISTRY["Scalability Score"]),
            ("Innovation Score",  _INNOVATION_CRITERIA,   _extract_innovation,  _innovation_action,  _ANOMALY_REGISTRY["Innovation Score"]),
            ("Operational Score", _OPERATIONAL_CRITERIA,  _extract_operational, _operational_action, _ANOMALY_REGISTRY["Operational Score"]),
            ("Green Score",       _GREEN_CRITERIA,        _extract_green,       _green_action,       _ANOMALY_REGISTRY["Green Score"]),
        ]
 
        for dim_name, criteria, extractor, action_fn, anomalies in dimensions:
            try:
                score = _build_score(
                    name=dim_name,
                    profile=profile,
                    criteria=criteria,
                    raw_extractor=extractor,
                    action_fn=action_fn,
                    anomaly_rules=anomalies,
                    lambda_penalty=self.lambda_penalty,
                )
                scores.append(score)
            except Exception as exc:  # noqa: BLE001
                # One dimension failing must not block the full analysis.
                logger.error("Scoring dimension '%s' failed: %s", dim_name, exc, exc_info=True)
                # Return a zero-confidence, zero-value fallback Score so
                # downstream consumers don't crash on a missing dimension.
                scores.append(Score(
                    name=dim_name,
                    value=0.0,
                    confidence=0.0,
                    sub_scores=[],
                    missing_criteria=["scoring_error"],
                    anomalies=[f"scoring_error: {exc!s}"],
                    highest_leverage_action="Scoring service encountered an error for this dimension. Contact support.",
                    triggered_rules=[],
                    version=SCORING_VERSION,
                ))
 
        return CompositeScores(scores=scores, version=SCORING_VERSION)
 
    # ── Convenience helpers for downstream services ────────────────────────
 
    @staticmethod
    def weak_scores(scores: CompositeScores, threshold: float = WEAK_SCORE_THRESHOLD) -> dict[str, Score]:
        """
        Return scores below *threshold* (default 55).
 
        Used by resource_service:
            weak = calculator.weak_scores(scores)
            # → match KB resources whose score_focus intersects weak.keys()
        """
        return {s.name: s for s in scores.scores if s.value < threshold}
 
    @staticmethod
    def green_band(green_score_value: float) -> str:
        """
        Map a Green Score value (0–100) to the environmental impact band
        from Image 2's classification table (rescaled from 0–20 to 0–100).
 
          0–35   → Très faible impact
          36–55  → Faible impact
          56–75  → Impact modéré
          76–90  → Impact élevé
          91–100 → Impact très élevé
        """
        if green_score_value <= 35:
            return "Très faible impact"
        if green_score_value <= 55:
            return "Faible impact"
        if green_score_value <= 75:
            return "Impact modéré"
        if green_score_value <= 90:
            return "Impact élevé"
        return "Impact très élevé"


class ModelBasedScoreCalculator:
    name = "model_based_scoring"
    version = "model-based-v0.1.0"

    def __init__(self) -> None:
        self.fallback = WeightedRuleScoreCalculator()

    def load(self) -> None:
        return None

    def calculate(self, profile: ProjectProfile) -> CompositeScores:
        scores = self.fallback.calculate(profile)
        return scores.model_copy(update={"version": self.version})

    def predict(self, payload: BaseModel) -> BaseModel:
        if not isinstance(payload, ProjectProfile):
            raise TypeError("ModelBasedScoreCalculator expects a ProjectProfile payload")
        return self.calculate(payload)
 
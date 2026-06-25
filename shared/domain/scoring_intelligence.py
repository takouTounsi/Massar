"""
MASSAR Scoring Intelligence Layer 

Every number that affects a founder's score, readiness, leverage ranking,
or profile state in this module is produced by deterministic Python:
WeightedRuleScoreCalculator, GraphWeightedReadinessEngine,
CounterfactualEngine, ContextualMutationEngine, and the dependency-graph /
contribution-analysis math. 

The LLM (Qwen3-32B on Groq, free tier) is wired into exactly six narrow
seams, and every one of them receives already-computed numbers as INPUT
and produces TEXT as output.
The six seams are:
  1. _generate_archetype_narrative()   — turns detector signals into prose
  2. _sequence_recommendations()       — orders already-ranked actions
  3. _build_swot_prompt() (enhanced)   — grounds SWOT in readiness/bottlenecks
  4. _generate_milestone_rationale()   — explains why one action matters
  5. (offline, see scripts/generate_sector_kb.py) — sector action libraries
  6. _generate_board_summary()         — executive narrative

Each seam has a deterministic fallback (used when GROQ_API_KEY is unset or
the call fails) so the system degrades to "no narrative" rather than
"wrong narrative" or "crash."


ADDING A NEW SECTOR
  1. Subclass SectorStrategy in the "decision layer" section below,
     implement build_mutation_patch() with deterministic field deltas.
  2. Register in SectorStrategyRegistry._REGISTRY.
  3. Add Layer 2 templates in SectorAwareActionGenerator._sector_actions(),
     OR generate them offline via scripts/generate_sector_kb.py and load
     them through SectorKnowledgeBase.
"""

from __future__ import annotations
import requests
import copy
import json
import logging
import math
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError

logger = logging.getLogger(__name__)

# Local imports — adjust paths to your project layout
try:
    from shared.contracts.schemas import CompositeScores, ProjectProfile, Score, SubScore
    from shared.contracts.enums import EvidenceStatus, MaturityStage
    from shared.domain.scoring import (
        WeightedRuleScoreCalculator,
        _MARKET_CRITERIA,
        _SCALABILITY_CRITERIA,
        _INNOVATION_CRITERIA,
        _OPERATIONAL_CRITERIA,
        _GREEN_CRITERIA,
        CriterionSpec,
        LAMBDA_DEFAULT,
    )
    _CONTRACTS_AVAILABLE = True
except ImportError:
    logger.warning("shared.contracts not found — running in stub mode.")
    _CONTRACTS_AVAILABLE = False
    CompositeScores = Any  # type: ignore[misc,assignment]
    ProjectProfile = Any   # type: ignore[misc,assignment]
    Score = Any            # type: ignore[misc,assignment]
    SubScore = Any         # type: ignore[misc,assignment]
    EvidenceStatus = Any   # type: ignore[misc,assignment]
    WeightedRuleScoreCalculator = None  # type: ignore[misc,assignment]
    _MARKET_CRITERIA = []
    _SCALABILITY_CRITERIA = []
    _INNOVATION_CRITERIA = []
    _OPERATIONAL_CRITERIA = []
    _GREEN_CRITERIA = []

    class MaturityStage(str, Enum):  # type: ignore[no-redef]
        IDEATION = "IDEATION"
        MARKET_VALIDATION = "MARKET_VALIDATION"
        STRUCTURATION = "STRUCTURATION"
        FUNDRAISING = "FUNDRAISING"
        LAUNCH_PLANNING = "LAUNCH_PLANNING"
        GROWTH = "GROWTH"

    @dataclass
    class CriterionSpec:  # type: ignore[no-redef]
        name: str
        field: str
        weight: float
        fundamental: bool = False
        extractor: Any = None
        rule_id: str = ""

    LAMBDA_DEFAULT = 0.5

# Module-level constants
_INTELLIGENCE_VERSION = "intelligence-v4.0.0"

_ALL_CRITERIA: dict[str, list] = {
    "Market Score":      _MARKET_CRITERIA,
    "Scalability Score": _SCALABILITY_CRITERIA,
    "Innovation Score":  _INNOVATION_CRITERIA,
    "Operational Score": _OPERATIONAL_CRITERIA,
    "Green Score":       _GREEN_CRITERIA,
}

# Readiness dimension weights — must sum to 1.0. 
_READINESS_WEIGHTS: dict[str, float] = {
    "Market Score":      0.30,
    "Operational Score": 0.25,
    "Scalability Score": 0.20,
    "Innovation Score":  0.15,
    "Green Score":       0.10,
}
assert abs(sum(_READINESS_WEIGHTS.values()) - 1.0) < 1e-9

# Effort taxonomy (founder-weeks). Only effort is hardcoded — gains are
# always computed by CounterfactualEngine.
class EffortCost(float, Enum):
    TRIVIAL   = 0.5   # < 1 day: upload document
    LOW       = 1.5   # 1–3 days: write analysis, run interviews
    MEDIUM    = 3.0   # 1–2 weeks: build artifact, run study
    HIGH      = 6.0   # 2–6 weeks: build MVP, legal registration
    VERY_HIGH = 12.0  # 1–3 months: full product, fund application

# Sector identifiers
class Sector(str, Enum):
    SAAS       = "saas"
    DEEPTECH   = "deeptech"
    GREENTECH  = "greentech"
    FINTECH    = "fintech"
    HEALTHTECH = "healthtech"
    OTHER      = "other"


# OUTPUT DATA MODELS
@dataclass
class ScoreDelta:
    """Actual score change from counterfactual recomputation."""
    score_name: str
    before: float
    after: float
    delta: float
    confidence_before: float
    confidence_after: float
    confidence_delta: float


@dataclass
class MutationSet:
    """
    Concrete profile mutations produced by ContextualMutationEngine.
    Carries full audit trail of contributing strategies.

    """
    action_id: str
    field_mutations: dict[str, Any]
    evidence_confirmations: list[str]
    strategy_trace: list[str]
    assumptions: list[str]


@dataclass
class CounterfactualResult:
    """
    produced entirely by CounterfactualEngine.
    The LLM may read this dataclass (e.g. in _sequence_recommendations or
    _generate_milestone_rationale) 
    """
    action_id: str
    action_title: str
    effort: float
    mutation_set: MutationSet
    score_deltas: list[ScoreDelta]
    overall_readiness_before: float
    overall_readiness_after: float
    overall_readiness_gain: float
    leverage: float
    sector: str
    stage: str
    contextual_notes: list[str]


@dataclass
class ReadinessContribution:
    """One dimension's contribution to the graph-weighted readiness score."""
    dimension: str
    raw_score: float
    weight: float
    confidence: float
    confidence_adjusted_score: float
    dependency_multiplier: float
    effective_score: float
    weighted_contribution: float


@dataclass
class ReadinessReport:
    """
    Readiness report is produced entirely by GraphWeightedReadinessEngine.
    All values are explainable from the documented formula. The LLM may
    quote these numbers verbatim in narrative text.
    """
    overall_readiness: float
    readiness_without_penalty: float      # Geometric mean without dep. multipliers
    confidence_adjusted_readiness: float  # Weighted mean of conf-adjusted scores
    bottleneck_cost: float                # readiness_without_penalty - overall_readiness
    weakest_link_floor: float             # Lowest effective_score
    contributions: list[ReadinessContribution]
    formula_trace: str


@dataclass
class Milestone:
    id: str
    title: str
    description: str               # deterministic, from CandidateAction
    rationale: str                 # LLM-generated explanation (seam 4) — may be empty string
    horizon: str
    addresses_score: str
    addresses_criteria: list[str]
    blocked_by: list[str]
    resource_tags: list[str]
    effort: float
    sector: str
    layer: str                   # "universal" | "sector" | "archetype"
    projected_score_deltas: list[ScoreDelta]
    overall_readiness_gain: float
    leverage: float
    mutation_set: MutationSet
    contextual_notes: list[str]


@dataclass
class SequencedStep:
    """
    One entry in the LLM-produced execution sequence (seam 2).
    `dependencies` here is an explanation surface only — it must be a
    subset of what the deterministic dependency graph already computed
    (Milestone.blocked_by).
    """
    title: str
    rationale: str
    dependencies: list[str]
    milestone_id: str | None = None


@dataclass
class MilestoneRoadmap:
    milestones: list[Milestone]
    critical_path: list[str]
    overall_readiness_now: float
    overall_readiness_after_all: float
    readiness_report: ReadinessReport
    sequence_narrative: list[SequencedStep] = field(default_factory=list)
    sequencing_generated_by: str = "deterministic"


@dataclass
class ResourceRecommendation:
    category: str
    name: str
    description: str
    url: str
    relevance_explanation: str
    score_focus: str
    eligibility_met: bool
    similarity_score: float
    priority: int


@dataclass
class CriterionContribution:
    criterion_name: str
    weight: float
    raw_value: float
    weighted_contribution: float
    is_fundamental: bool
    lambda_penalty_exposure: float
    evidence_status: str
    evidence_cost: float
    is_weakest_fundamental: bool


@dataclass
class ScoreDecomposition:
    score_name: str
    composite_value: float
    c_base: float
    lambda_penalty_cost: float
    lambda_penalty_fraction: float
    weakest_fundamental_criterion: str | None
    weakest_fundamental_value: float | None
    criterion_contributions: list[CriterionContribution]
    anomaly_penalties: list[str]
    anomaly_confidence_cost: float
    top_reduction_causes: list[str]
    missing_evidence_cost: float
    confidence_value: float


@dataclass
class ScoreExplanation:
    score_name: str
    decomposition: ScoreDecomposition
    bottleneck_explanation: str | None
    high_score_low_confidence_signal: str | None
    quick_wins: list[str]


@dataclass
class GraphNode:
    node_id: str
    node_type: str
    score_name: str | None
    current_value: float
    weight_in_parent: float
    is_fundamental: bool
    marginal_gain_if_maxed: float


@dataclass
class BottleneckAnalysis:
    bottleneck_node_id: str
    bottleneck_type: str
    blocked_potential: float
    explanation: str
    improving_others_first_explanation: str


@dataclass
class SWOTAnalysis:
    strengths: list[str]
    weaknesses: list[str]
    opportunities: list[str]
    threats: list[str]
    generated_by: str


@dataclass
class ArchetypeSignal:
    signal_id: str
    description: str
    evidence: str


@dataclass
class FounderArchetype:
    """
    Detection fields (archetype_id, secondary_archetype_id, confidence,
    evidence_quality, triggering_signals, next_stage_gate) are produced
    entirely by the deterministic ArchetypeEngine.detect().

    pattern_description and strategic_recommendation are produced by
    _generate_archetype_narrative() (seam 1) — an LLM call grounded in
    the detection fields above. If the LLM is unavailable, these two
    fields fall back to short, signal-derived sentences.
    """
    archetype_id: str
    label: str
    secondary_archetype_id: str | None
    confidence: float                       # vote share of winning archetype
    evidence_quality: float                 # avg confidence across scores
    pattern_description: str
    triggering_signals: list[ArchetypeSignal]
    strategic_recommendation: str
    co_founder_fit: str
    next_stage_gate: str
    narrative_generated_by: str = "deterministic"


@dataclass
class ConfidenceSignal:
    score_name: str
    current_score: float
    current_confidence: float
    criterion_name: str
    criterion_weight: float
    upload_action: str
    expected_confidence_gain: float


@dataclass
class BoardSummary:
    """
    Output of seam 6 (_generate_board_summary). Pure narrative — every
    sentence must be traceable to a number already present in
    ReadinessReport / BottleneckAnalysis / ContributionAnalysis /
    FounderArchetype / top CounterfactualResults.
    """
    executive_summary: str
    key_risk: str
    main_opportunity: str
    strategic_focus: str
    generated_by: str = "deterministic"


@dataclass
class IntelligenceReport:
    roadmap: MilestoneRoadmap
    resources: list[ResourceRecommendation]
    top_actions: list[CounterfactualResult]
    explanations: list[ScoreExplanation]
    bottlenecks: list[BottleneckAnalysis]
    swot: SWOTAnalysis
    archetype: FounderArchetype
    confidence_signals: list[ConfidenceSignal]
    readiness_report: ReadinessReport
    board_summary: BoardSummary
    overall_readiness: float
    generated_by: str = _INTELLIGENCE_VERSION


@dataclass
class CandidateAction:
    """
    A proposed action with base (sector-agnostic) mutations.
    ContextualMutationEngine enriches these before counterfactual evaluation.
    """
    action_id: str
    title: str
    description: str
    effort: float
    base_mutations: dict[str, Any]
    evidence_confirmations: list[str]
    addresses_criteria: list[str]
    resource_tags: list[str]
    layer: str                     # "universal" | "sector" | "archetype"
    base_assumptions: list[str]


# SHARED LLM CLIENT (Groq / Qwen3-32B) — used by seams 1, 2, 3, 4, 6
# This is the ONLY place that talks to the network for narrative purposes.
# Every caller passes a fully-formed prompt and a JSON schema description;
# this helper does not know anything about scoring semantics. That keeps
# the "LLM explains, never decides" boundary enforced structurally: the
# decision-layer engines never import this module, only the narrative
# builder functions below do.

_GROQ_MODEL = "llama-3.3-70b-versatile"
_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def _groq_chat_json(prompt, max_tokens=700, temperature=0.3):

    api_key = os.environ.get("GROQ_API_KEY")

    if not api_key:
        return None

    try:

        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": temperature,
                "max_completion_tokens": max_tokens
            },
            timeout=30
        )

        response.raise_for_status()

        body = response.json()

        raw = body["choices"][0]["message"]["content"]

        raw = raw.replace("```json", "")
        raw = raw.replace("```", "")
        raw = raw.strip()

        return json.loads(raw)

    except Exception as e:
        logger.exception(e)
        return None

async def _groq_chat_json_async(prompt: str, max_tokens: int = 700, temperature: float = 0.3) -> dict[str, Any] | None:
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _groq_chat_json, prompt, max_tokens, temperature)


# 1. GRAPH WEIGHTED READINESS ENGINE 

class GraphWeightedReadinessEngine:
    """
    Computes overall readiness via a weighted geometric mean with three
    correction layers. 

    FORMULA
    -------
    Step 1 — Confidence-adjusted score per dimension d:
        conf_adj(d) = raw_score(d) × confidence(d)^α    α = 0.3

    Step 2 — Dependency multiplier via the prerequisite chain:
        Prerequisite chain: Innovation → Operational → Market → Scalability
        dep_multiplier(d) = Π sigmoid(eff_score(prereq) / 50) for each prereq
        sigmoid(x) = 0.5 + 0.5×(prereq_score/100)

    Step 3 — Effective score per dimension:
        effective(d) = conf_adj(d) × dep_multiplier(d)

    Step 4 — Weighted geometric mean over effective scores:
        G = exp( Σ_d  w_d × ln(max(effective(d), 0.1)) )

    Step 5 — Weakest-link floor:
        If min(effective) < FLOOR_THRESHOLD (=20):
            overall = min(G, min_effective × FLOOR_MULTIPLIER (=1.5))
    """

    _CONFIDENCE_ALPHA = 0.3
    _FLOOR_THRESHOLD  = 20.0
    _FLOOR_MULTIPLIER = 1.5

    _DEPENDENCY_GRAPH: dict[str, list[str]] = {
        "Market Score":      ["Operational Score"],
        "Scalability Score": ["Market Score", "Operational Score"],
        "Innovation Score":  [],
        "Operational Score": ["Innovation Score"],
        "Green Score":       [],
    }

    def compute(self, scores: Any) -> ReadinessReport:
        by_name = {s.name: s for s in scores.scores}

        conf_adj: dict[str, float] = {}
        contributions: list[ReadinessContribution] = []
        for dim, weight in _READINESS_WEIGHTS.items():
            s = by_name.get(dim)
            raw = s.value if s else 0.0
            conf = s.confidence if s else 0.0
            ca = raw * (conf ** self._CONFIDENCE_ALPHA)
            conf_adj[dim] = ca
            contributions.append(ReadinessContribution(
                dimension=dim, raw_score=round(raw, 2), weight=weight,
                confidence=round(conf, 3), confidence_adjusted_score=round(ca, 2),
                dependency_multiplier=1.0, effective_score=round(ca, 2),
                weighted_contribution=0.0,
            ))

        def _dep_mult(prereq_score: float) -> float:
            return 0.5 + 0.5 * (prereq_score / 100.0)

        cmap = {c.dimension: c for c in contributions}
        effective: dict[str, float] = dict(conf_adj)
        for dim in _READINESS_WEIGHTS:
            prereqs = self._DEPENDENCY_GRAPH.get(dim, [])
            if not prereqs:
                continue
            mult = 1.0
            for p in prereqs:
                mult *= _dep_mult(effective.get(p, 0.0))
            effective[dim] = conf_adj[dim] * mult
            cmap[dim].dependency_multiplier = round(mult, 4)
            cmap[dim].effective_score = round(effective[dim], 2)

        log_sum = log_sum_no_dep = conf_adj_sum = 0.0
        for dim, weight in _READINESS_WEIGHTS.items():
            eff = effective.get(dim, 0.0)
            ca = conf_adj.get(dim, 0.0)
            log_sum += weight * math.log(max(eff, 0.1))
            log_sum_no_dep += weight * math.log(max(ca, 0.1))
            conf_adj_sum += weight * ca
            cmap[dim].weighted_contribution = round(weight * eff, 3)

        geo_mean = math.exp(log_sum)
        geo_no_dep = math.exp(log_sum_no_dep)

        weakest_eff = min(effective.values()) if effective else 0.0
        if weakest_eff < self._FLOOR_THRESHOLD:
            overall = min(geo_mean, weakest_eff * self._FLOOR_MULTIPLIER)
        else:
            overall = geo_mean
        overall = min(overall, 100.0)

        bottleneck_cost = max(0.0, geo_no_dep - overall)

        trace = ["GraphWeightedReadinessEngine v4 (deterministic, unchanged from v3):"]
        trace.append(f"  Weights: {', '.join(f'{d.split()[0]}={w:.0%}' for d, w in _READINESS_WEIGHTS.items())}")
        trace.append(f"  α (confidence exponent): {self._CONFIDENCE_ALPHA}")
        for c in contributions:
            trace.append(
                f"  {c.dimension}: raw={c.raw_score:.1f}, conf={c.confidence:.2f}, "
                f"conf_adj={c.confidence_adjusted_score:.1f}, dep_mult={c.dependency_multiplier:.3f}, "
                f"effective={c.effective_score:.1f}, contrib={c.weighted_contribution:.3f}"
            )
        trace.append(f"  Geometric mean (no dep penalty): {geo_no_dep:.2f}")
        trace.append(f"  Weakest effective score: {weakest_eff:.1f} (floor threshold={self._FLOOR_THRESHOLD})")
        trace.append(f"  Floor applied: {'yes' if weakest_eff < self._FLOOR_THRESHOLD else 'no'}")
        trace.append(f"  Overall readiness: {overall:.2f}")

        return ReadinessReport(
            overall_readiness=round(overall, 2),
            readiness_without_penalty=round(geo_no_dep, 2),
            confidence_adjusted_readiness=round(conf_adj_sum, 2),
            bottleneck_cost=round(bottleneck_cost, 2),
            weakest_link_floor=round(weakest_eff, 2),
            contributions=list(contributions),
            formula_trace="\n".join(trace),
        )


# 2. CONTEXTUAL MUTATION ENGINE 

class SectorStrategy(ABC):
    """
    Abstract base for sector mutation strategies.

    ADDING A NEW SECTOR:
      1. Subclass SectorStrategy, implement build_mutation_patch() and sector_id
      2. Register in SectorStrategyRegistry._REGISTRY
      3. Add Layer 2 templates in SectorAwareActionGenerator._sector_actions(),
         or generate them offline and load via SectorKnowledgeBase.
    """

    @abstractmethod
    def build_mutation_patch(
        self,
        action_id: str,
        base_mutations: dict[str, Any],
        profile: Any,
        stage: str,
        trl: int | None,
        archetype_id: str,
        scores_by_name: dict[str, Any],
    ) -> tuple[dict[str, Any], list[str], list[str]]:
        ...

    @property
    @abstractmethod
    def sector_id(self) -> str:
        ...


class SaaSStrategy(SectorStrategy):
    """SaaS MVPs ship as working web products and inherently automate workflows."""

    @property
    def sector_id(self) -> str:
        return Sector.SAAS

    def build_mutation_patch(self, action_id, base_mutations, profile, stage, trl, archetype_id, scores_by_name):
        patch: dict[str, Any] = {}
        evidence: list[str] = []
        assumptions: list[str] = []

        if base_mutations.get("has_mvp") is True:
            auto = getattr(profile, "process_automation_level", 0.0) or 0.0
            patch["process_automation_level"] = min(auto + 0.15, 1.0)
            cust = getattr(profile, "paying_customers", 0) or 0
            patch["paying_customers"] = cust + 1
            rev = getattr(profile, "revenue_model_clarity", 0) or 0
            patch["revenue_model_clarity"] = min(rev + 15, 100)
            evidence += ["has_mvp", "process_automation_level", "paying_customers"]
            assumptions += [
                "SaaS MVP shipped as a working web/mobile product.",
                f"process_automation_level +0.15 (from {auto:.2f}) — SaaS inherently automates its workflows.",
                "First paying customer acquired via digital distribution.",
                "Early pricing experiment produced +15 revenue_model_clarity.",
            ]

        if "paying_customers" in base_mutations:
            comp = getattr(profile, "competition_understanding", 0) or 0
            patch["competition_understanding"] = min(comp + 10, 100)
            evidence.append("paying_customers")
            assumptions.append("SaaS pilot customers provide competitive feedback (+10 competition_understanding).")

        if "process_automation_level" in base_mutations:
            tss = getattr(profile, "tech_stack_scalability", 0) or 0
            patch["tech_stack_scalability"] = min(tss + 10, 100)
            assumptions.append("SaaS automation improvements co-improve tech_stack_scalability (+10).")

        return patch, evidence, assumptions


class DeepTechStrategy(SectorStrategy):
    """DeepTech MVPs require TRL progression; IP filing co-occurs with validated prototypes."""

    @property
    def sector_id(self) -> str:
        return Sector.DEEPTECH

    def build_mutation_patch(self, action_id, base_mutations, profile, stage, trl, archetype_id, scores_by_name):
        patch: dict[str, Any] = {}
        evidence: list[str] = []
        assumptions: list[str] = []
        current_trl = trl or getattr(profile, "technology_readiness_level", 1) or 1

        if base_mutations.get("has_mvp") is True:
            new_trl = min(current_trl + 1, 9)
            patch["technology_readiness_level"] = new_trl
            ip = list(getattr(profile, "ip_assets", []) or [])
            if not ip:
                patch["ip_assets"] = ["provisional_patent"]
                evidence.append("ip_assets")
                assumptions.append("DeepTech MVP triggers provisional patent filing.")
            novelty = getattr(profile, "problem_novelty_score", 50) or 50
            patch["problem_novelty_score"] = min(novelty + 10, 100)
            evidence += ["has_mvp", "technology_readiness_level"]
            assumptions += [
                f"DeepTech MVP advances TRL {current_trl} → {new_trl}.",
                "Technical validation document produced (test protocols + results).",
                "problem_novelty_score +10 from formal novelty documentation.",
            ]

        if "technology_readiness_level" in base_mutations:
            rd = getattr(profile, "rd_investment_ratio", 0.0) or 0.0
            patch["rd_investment_ratio"] = min(rd + 0.05, 1.0)
            evidence.append("technology_readiness_level")
            assumptions.append(f"TRL advancement implies R&D investment (+0.05 from {rd:.2f}).")

        if "ip_assets" in base_mutations:
            novelty = getattr(profile, "problem_novelty_score", 0) or 0
            patch["problem_novelty_score"] = min(novelty + 15, 100)
            evidence.append("ip_assets")
            assumptions.append("IP filing requires formal novelty documentation (+15 problem_novelty_score).")

        return patch, evidence, assumptions


class GreenTechStrategy(SectorStrategy):
    """GreenTech MVPs must include environmental baseline measurement."""

    @property
    def sector_id(self) -> str:
        return Sector.GREENTECH

    def build_mutation_patch(self, action_id, base_mutations, profile, stage, trl, archetype_id, scores_by_name):
        patch: dict[str, Any] = {}
        evidence: list[str] = []
        assumptions: list[str] = []

        if base_mutations.get("has_mvp") is True:
            patch["climate_air_impact_score"] = min((getattr(profile, "climate_air_impact_score", 0) or 0) + 20, 100)
            patch["resources_waste_score"]     = min((getattr(profile, "resources_waste_score", 0) or 0) + 15, 100)
            patch["sdg_alignment_score"]       = min((getattr(profile, "sdg_alignment_score", 0) or 0) + 20, 100)
            evidence += ["has_mvp", "climate_air_impact_score", "sdg_alignment_score"]
            assumptions += [
                "GreenTech MVP ships with documented environmental baseline.",
                "SDG alignment statement produced as part of MVP documentation (+20 sdg_alignment_score).",
                "Climate/air impact baseline measured and reported (+20).",
                "Resources & waste audit completed alongside MVP (+15).",
            ]

        _green_fields = {"climate_air_impact_score", "water_impact_score", "soil_biodiversity_score", "resources_waste_score"}
        if any(f in base_mutations for f in _green_fields):
            sdg = getattr(profile, "sdg_alignment_score", 0) or 0
            patch["sdg_alignment_score"] = min(sdg + 15, 100)
            evidence.append("sdg_alignment_score")
            assumptions.append("Environmental pillar measurement co-produces SDG alignment evidence (+15).")

        return patch, evidence, assumptions


class FinTechStrategy(SectorStrategy):
    """FinTech MVPs require regulatory compliance before paying customers."""

    @property
    def sector_id(self) -> str:
        return Sector.FINTECH

    def build_mutation_patch(self, action_id, base_mutations, profile, stage, trl, archetype_id, scores_by_name):
        patch: dict[str, Any] = {}
        evidence: list[str] = []
        assumptions: list[str] = []

        if base_mutations.get("has_mvp") is True:
            patch["legal_compliance_score"]  = min((getattr(profile, "legal_compliance_score", 0) or 0) + 20, 100)
            patch["financial_model_quality"] = min((getattr(profile, "financial_model_quality", 0) or 0) + 15, 100)
            cust = getattr(profile, "paying_customers", 0) or 0
            patch["paying_customers"] = cust + 1
            evidence += ["has_mvp", "legal_compliance_score", "paying_customers"]
            assumptions += [
                "FinTech MVP passes BCT/APTBEF regulatory sandbox review.",
                "Legal compliance checklist completed as pre-condition for launch (+20).",
                "Financial model formalised for regulatory submission (+15).",
                "First paying customer acquired post-clearance.",
            ]

        if "legal_compliance_score" in base_mutations:
            patch["market_size_known"] = True
            evidence.append("legal_compliance_score")
            assumptions.append("FinTech regulatory clearance enables formal market sizing.")

        if "paying_customers" in base_mutations:
            rev = getattr(profile, "revenue_model_clarity", 0) or 0
            patch["revenue_model_clarity"] = min(rev + 20, 100)
            evidence.append("paying_customers")
            assumptions.append("FinTech paying customers produce documented transaction revenue model (+20).")

        return patch, evidence, assumptions


class HealthTechStrategy(SectorStrategy):
    """
    HealthTech MVPs require clinical/regulatory groundwork before customer
    acquisition is credible. Modeled after FinTech's compliance-gate shape,
    with health-specific evidence fields.
    """

    @property
    def sector_id(self) -> str:
        return Sector.HEALTHTECH

    def build_mutation_patch(self, action_id, base_mutations, profile, stage, trl, archetype_id, scores_by_name):
        patch: dict[str, Any] = {}
        evidence: list[str] = []
        assumptions: list[str] = []

        if base_mutations.get("has_mvp") is True:
            patch["legal_compliance_score"] = min((getattr(profile, "legal_compliance_score", 0) or 0) + 25, 100)
            novelty = getattr(profile, "problem_novelty_score", 0) or 0
            patch["problem_novelty_score"] = min(novelty + 10, 100)
            evidence += ["has_mvp", "legal_compliance_score"]
            assumptions += [
                "HealthTech MVP requires a documented regulatory/ethics pathway before pilot use.",
                "Legal/regulatory compliance score +25 from initial clinical-governance documentation.",
                "problem_novelty_score +10 from formal clinical-need documentation.",
            ]

        if "legal_compliance_score" in base_mutations:
            cust = getattr(profile, "paying_customers", 0) or 0
            patch["paying_customers"] = cust  # compliance unlocks, does not itself create, customers
            evidence.append("legal_compliance_score")
            assumptions.append("Regulatory clearance is a precondition for HealthTech customer acquisition, not a customer itself.")

        return patch, evidence, assumptions


class DefaultStrategy(SectorStrategy):
    """Fallback: no sector-specific enrichment."""

    @property
    def sector_id(self) -> str:
        return Sector.OTHER

    def build_mutation_patch(self, action_id, base_mutations, profile, stage, trl, archetype_id, scores_by_name):
        return {}, [], ["No sector-specific mutations applied (sector: other)."]


class StageStrategy:
    """Scales numeric field mutations by a maturity-stage multiplier. DECISION LAYER."""

    _MULTIPLIERS: dict[str, float] = {
        "IDEATION":          0.70,
        "MARKET_VALIDATION": 0.85,
        "STRUCTURATION":     0.95,
        "FUNDRAISING":       1.05,
        "LAUNCH_PLANNING":   1.10,
        "GROWTH":            1.20,
    }

    def apply(self, mutations: dict[str, Any], stage: str) -> tuple[dict[str, Any], list[str]]:
        mult = self._MULTIPLIERS.get(stage, 1.0)
        adjusted: dict[str, Any] = {}
        for k, v in mutations.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                adjusted[k] = type(v)(v * mult)
            else:
                adjusted[k] = v
        assumptions = []
        if mult != 1.0:
            assumptions.append(
                f"Stage '{stage}' (×{mult:.2f}): numeric mutations scaled — "
                f"{'above' if mult > 1.0 else 'below'} baseline for this maturity level."
            )
        return adjusted, assumptions


class TRLStrategy:
    """Adjusts technology-related field mutations based on current TRL. DECISION LAYER."""

    _TECH_FIELDS = {
        "technology_readiness_level", "problem_novelty_score",
        "rd_investment_ratio", "tech_stack_scalability", "infrastructure_readiness",
    }

    def apply(self, mutations: dict[str, Any], trl: int | None) -> tuple[dict[str, Any], list[str]]:
        if trl is None:
            return mutations, []
        if trl <= 3:
            mult, note = 0.75, f"TRL={trl} (concept): tech mutations dampened ×0.75."
        elif trl >= 7:
            mult, note = 1.20, f"TRL={trl} (prototype+): tech mutations amplified ×1.20."
        else:
            return mutations, []

        adjusted: dict[str, Any] = {}
        for k, v in mutations.items():
            if k in self._TECH_FIELDS and isinstance(v, (int, float)) and not isinstance(v, bool):
                adjusted[k] = type(v)(v * mult)
            else:
                adjusted[k] = v
        return adjusted, [note]


class SectorStrategyRegistry:
    """Registry of all sector strategies. DECISION LAYER. To add a sector: add to _REGISTRY."""

    _REGISTRY: dict[str, SectorStrategy] = {
        Sector.SAAS:       SaaSStrategy(),
        Sector.DEEPTECH:   DeepTechStrategy(),
        Sector.GREENTECH:  GreenTechStrategy(),
        Sector.FINTECH:    FinTechStrategy(),
        Sector.HEALTHTECH: HealthTechStrategy(),
        Sector.OTHER:      DefaultStrategy(),
    }

    @classmethod
    def get(cls, sector_hint: str) -> SectorStrategy:
        h = sector_hint.lower().replace("-", "").replace(" ", "")
        if any(k in h for k in ("saas", "software", "app", "platform")):
            return cls._REGISTRY[Sector.SAAS]
        if any(k in h for k in ("deep", "hardware", "robotics")):
            return cls._REGISTRY[Sector.DEEPTECH]
        if any(k in h for k in ("health", "medtech", "biotech", "clinical")):
            return cls._REGISTRY[Sector.HEALTHTECH]
        if any(k in h for k in ("green", "climate", "energy", "environ", "sustain")):
            return cls._REGISTRY[Sector.GREENTECH]
        if any(k in h for k in ("fin", "payment", "bank", "insurtech", "crypto")):
            return cls._REGISTRY[Sector.FINTECH]
        return cls._REGISTRY[Sector.OTHER]

    @classmethod
    def detect_sector(cls, profile: Any) -> str:
        combined = (
            (getattr(profile, "sector", "") or "") + " " +
            (getattr(profile, "sub_sector", "") or "")
        )
        return cls.get(combined).sector_id


class ContextualMutationEngine:
    """
    Produces a MutationSet for a (action, profile) pair via three
    deterministic strategy layers (sector -> stage -> TRL). 
    """

    def __init__(self) -> None:
        self._stage = StageStrategy()
        self._trl = TRLStrategy()

    def build(
        self,
        action: CandidateAction,
        profile: Any,
        scores_by_name: dict[str, Any],
        archetype_id: str,
    ) -> MutationSet:
        sector = SectorStrategyRegistry.detect_sector(profile)
        strategy = SectorStrategyRegistry.get(sector)
        stage = str(getattr(profile, "effective_stage", "IDEATION"))
        trl = getattr(profile, "technology_readiness_level", None)

        sector_patch, sector_evidence, sector_assumptions = strategy.build_mutation_patch(
            action_id=action.action_id,
            base_mutations=action.base_mutations,
            profile=profile,
            stage=stage,
            trl=trl,
            archetype_id=archetype_id,
            scores_by_name=scores_by_name,
        )

        merged: dict[str, Any] = {**action.base_mutations, **sector_patch}
        merged, stage_assumptions = self._stage.apply(merged, stage)
        merged, trl_assumptions = self._trl.apply(merged, trl)
        merged = _clamp_profile_fields(merged)

        all_evidence = list(set(action.evidence_confirmations + sector_evidence))

        return MutationSet(
            action_id=action.action_id,
            field_mutations=merged,
            evidence_confirmations=all_evidence,
            strategy_trace=[
                f"base: {list(action.base_mutations.keys())}",
                f"sector ({sector}): adds {list(sector_patch.keys())}",
                f"stage ({stage}): multiplier={self._stage._MULTIPLIERS.get(stage, 1.0)}",
                f"trl ({trl}): {'adjusted' if trl and (trl <= 3 or trl >= 7) else 'no adjustment'}",
            ],
            assumptions=(
                action.base_assumptions + sector_assumptions + stage_assumptions + trl_assumptions
            ),
        )


def _clamp_profile_fields(mutations: dict[str, Any]) -> dict[str, Any]:
    """Clamp mutated values to valid ProjectProfile field ranges."""
    INT_0_100  = {"revenue_model_clarity", "competition_understanding", "innovation_level",
                  "process_documentation_score", "financial_model_quality", "legal_compliance_score",
                  "tech_stack_scalability", "infrastructure_readiness", "problem_novelty_score",
                  "climate_air_impact_score", "water_impact_score", "soil_biodiversity_score",
                  "resources_waste_score", "sdg_alignment_score", "financial_capacity_score"}
    FLOAT_0_1  = {"process_automation_level", "rd_investment_ratio"}
    INT_POS    = {"paying_customers", "team_size", "documented_interviews", "tender_references_count"}
    INT_TRL    = {"technology_readiness_level"}

    out: dict[str, Any] = {}
    for k, v in mutations.items():
        if k in INT_0_100 and isinstance(v, (int, float)):
            out[k] = int(max(0, min(100, v)))
        elif k in FLOAT_0_1 and isinstance(v, (int, float)):
            out[k] = float(max(0.0, min(1.0, v)))
        elif k in INT_POS and isinstance(v, (int, float)):
            out[k] = max(0, int(v))
        elif k in INT_TRL and isinstance(v, (int, float)):
            out[k] = int(max(1, min(9, v)))
        else:
            out[k] = v
    return out


# 3. COUNTERFACTUAL ENGINE 

class CounterfactualEngine:
    """
    Applies a MutationSet to a deep copy of ProjectProfile, reruns
    WeightedRuleScoreCalculator, and computes exact score deltas.
    Readiness before/after comes from GraphWeightedReadinessEngine.

    """

    def __init__(self, calculator: Any, readiness_engine: GraphWeightedReadinessEngine) -> None:
        self._calculator = calculator
        self._readiness = readiness_engine

    def run(
        self,
        mutation_set: MutationSet,
        action: CandidateAction,
        profile: Any,
        scores_before: Any,
        sector: str,
        stage: str,
        contextual_notes: list[str],
    ) -> CounterfactualResult:
        mutated = copy.deepcopy(profile)
        for fname, val in mutation_set.field_mutations.items():
            if hasattr(mutated, fname):
                setattr(mutated, fname, val)

        for fname in mutation_set.evidence_confirmations:
            try:
                from shared.contracts.schemas import EvidenceEntry
                from shared.contracts.enums import EvidenceStatus as ES
                mutated.evidence_ledger[fname] = EvidenceEntry(
                    status=ES.CONFIRMED,
                    source="counterfactual_simulation",
                    note=f"Contextual sim for '{mutation_set.action_id}'",
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "CounterfactualEngine: could not write evidence confirmation for "
                    "'%s' on action '%s' (%s) — confidence delta for this field will "
                    "read as zero. Check shared.contracts import path.",
                    fname, mutation_set.action_id, exc,
                )

        scores_after = self._calculator.compute(mutated) if self._calculator else scores_before

        bmap = {s.name: s for s in scores_before.scores}
        amap = {s.name: s for s in scores_after.scores}
        deltas = [
            ScoreDelta(
                score_name=dim,
                before=round(bmap[dim].value, 2),
                after=round(amap.get(dim, bmap[dim]).value, 2),
                delta=round(amap.get(dim, bmap[dim]).value - bmap[dim].value, 2),
                confidence_before=round(bmap[dim].confidence, 3),
                confidence_after=round(amap.get(dim, bmap[dim]).confidence, 3),
                confidence_delta=round(amap.get(dim, bmap[dim]).confidence - bmap[dim].confidence, 3),
            )
            for dim in bmap
        ]

        r_before = self._readiness.compute(scores_before)
        r_after  = self._readiness.compute(scores_after)
        gain = r_after.overall_readiness - r_before.overall_readiness
        leverage = gain / max(action.effort, 0.1)

        return CounterfactualResult(
            action_id=mutation_set.action_id,
            action_title=action.title,
            effort=action.effort,
            mutation_set=mutation_set,
            score_deltas=deltas,
            overall_readiness_before=round(r_before.overall_readiness, 2),
            overall_readiness_after=round(r_after.overall_readiness, 2),
            overall_readiness_gain=round(gain, 2),
            leverage=round(leverage, 3),
            sector=sector,
            stage=stage,
            contextual_notes=contextual_notes + mutation_set.strategy_trace,
        )


# 4. SECTOR-AWARE ACTION GENERATOR (3-layer)

class SectorAwareActionGenerator:
    """
    Three-layer CandidateAction generator. Generation rules derive from
    weakest criteria, anomalies, and missing fields — never from score
    thresholds.
    
    """

    def __init__(self, knowledge_base: "SectorKnowledgeBase | None" = None) -> None:
        # If a knowledge base of offline AI-generated templates is supplied,
        # it is used INSTEAD OF the hand-written _layer2_sector /
        # _layer3_archetype templates below for sectors it covers. The KB
        # itself is static JSON/YAML produced offline (seam 5)
        self._kb = knowledge_base

    def generate(
        self,
        profile: Any,
        scores: Any,
        archetype_id: str,
        bottlenecks: list[BottleneckAnalysis],
    ) -> list[CandidateAction]:
        sector = SectorStrategyRegistry.detect_sector(profile)
        stage = str(getattr(profile, "effective_stage", "IDEATION"))
        trl = getattr(profile, "technology_readiness_level", None)
        scores_by_name = {s.name: s for s in scores.scores}

        all_subs = [
            (spec, sub)
            for dim_name, criteria in _ALL_CRITERIA.items()
            for spec in criteria
            for s in scores_by_name.values() if s.name == dim_name
            for sub in s.sub_scores if sub.name == spec.name
        ]
        all_subs.sort(key=lambda x: x[1].value)
        weakest_criteria = {spec.name for spec, sub in all_subs[:8]}
        active_anomalies = [a for s in scores.scores for a in s.anomalies]
        missing_fields = [c for s in scores.scores for c in s.missing_criteria]

        actions: list[CandidateAction] = []
        seen: set[str] = set()

        def add(a: CandidateAction) -> None:
            if a.action_id not in seen:
                actions.append(a)
                seen.add(a.action_id)

        for a in self._layer1_universal(profile, scores_by_name, active_anomalies, missing_fields, weakest_criteria):
            add(a)

        # Layer 2: prefer offline AI-generated KB templates if available
        # for this sector, otherwise fall back to hand-written templates.
        kb_actions = self._kb.actions_for_sector(sector, profile) if self._kb else []
        if kb_actions:
            for a in kb_actions:
                add(a)
        else:
            for a in self._layer2_sector(sector, profile, scores_by_name, weakest_criteria, stage, trl, active_anomalies):
                add(a)

        for a in self._layer3_archetype(archetype_id, profile, scores_by_name, weakest_criteria, sector):
            add(a)

        return actions

    # ── Layer 1 

    def _layer1_universal(self, profile, scores_by_name, anomalies, missing_fields, weakest_criteria):
        actions: list[CandidateAction] = []

        for dim_name, criteria in _ALL_CRITERIA.items():
            score = scores_by_name.get(dim_name)
            if not score:
                continue
            for spec in criteria:
                ledger = getattr(profile, "evidence_ledger", {}) or {}
                entry = ledger.get(spec.field)
                status = str(entry.status) if entry else "absent"
                if status != "confirmed":
                    actions.append(CandidateAction(
                        action_id=f"upload_evidence_{spec.field}",
                        title=f"Confirm '{spec.name}' with uploaded artifact",
                        description=(
                            f"'{spec.name}' in {dim_name} is '{status}'. "
                            "Upload a supporting document to confirm and recover the confidence penalty."
                        ),
                        effort=float(EffortCost.TRIVIAL),
                        base_mutations={},
                        evidence_confirmations=[spec.field],
                        addresses_criteria=[spec.name],
                        resource_tags=[],
                        layer="universal",
                        base_assumptions=[f"'{spec.field}' artifact exists and needs uploading."],
                    ))

        _anomaly_map: dict[str, CandidateAction] = {
            "high_traction_no_documented_evidence": CandidateAction(
                action_id="resolve_high_traction_no_evidence",
                title="Upload customer evidence (traction/validation contradiction)",
                description="Paying customers claimed but no validation evidence. Upload contracts or invoices.",
                effort=float(EffortCost.TRIVIAL),
                base_mutations={"market_validation_evidence": ["customer_invoices", "contracts"]},
                evidence_confirmations=["market_validation_evidence", "paying_customers"],
                addresses_criteria=["Customer validation"],
                resource_tags=[],
                layer="universal",
                base_assumptions=["Customer transaction records exist in some form."],
            ),
            "revenue_without_mvp_artifact": CandidateAction(
                action_id="resolve_revenue_no_mvp",
                title="Upload MVP artifact (revenue/MVP contradiction)",
                description="Revenue reported without MVP. Upload product demo or transaction artifact.",
                effort=float(EffortCost.TRIVIAL),
                base_mutations={"has_mvp": True},
                evidence_confirmations=["has_mvp"],
                addresses_criteria=["MVP / product artifact"],
                resource_tags=[],
                layer="universal",
                base_assumptions=["MVP exists but is not recorded."],
            ),
            "high_innovation_claim_no_ip": CandidateAction(
                action_id="resolve_innovation_no_ip",
                title="File IP protection (innovation/IP contradiction)",
                description="High novelty claim with no IP. File provisional patent with INNORPI.",
                effort=float(EffortCost.MEDIUM),
                base_mutations={"ip_assets": ["provisional_patent"]},
                evidence_confirmations=["ip_assets"],
                addresses_criteria=["IP / moat strength"],
                resource_tags=["legal"],
                layer="universal",
                base_assumptions=["Innovation is defined well enough to describe in a filing."],
            ),
            "manual_processes_limit_growth": CandidateAction(
                action_id="resolve_manual_processes",
                title="Automate processes (stage/automation anomaly)",
                description="GROWTH stage with low automation. Automate top-3 manual operations.",
                effort=float(EffortCost.MEDIUM),
                base_mutations={"process_automation_level": 0.60},
                evidence_confirmations=["process_automation_level"],
                addresses_criteria=["Process automation level"],
                resource_tags=["tool"],
                layer="universal",
                base_assumptions=["Core operations are stable enough to automate."],
            ),
        }
        for anomaly_id in anomalies:
            if anomaly_id in _anomaly_map:
                actions.append(_anomaly_map[anomaly_id])

        _field_defaults: dict[str, tuple[str, str, dict, float]] = {
            "market_size_known":          ("Market Score", "Market-share potential",  {"market_size_known": True},          float(EffortCost.LOW)),
            "paying_customers":           ("Market Score", "Customer validation",     {"paying_customers": 5},              float(EffortCost.MEDIUM)),
            "has_mvp":                    ("Operational Score", "MVP / product artifact", {"has_mvp": True},                 float(EffortCost.HIGH)),
            "technology_readiness_level": ("Innovation Score", "Technological intensity (TRL)", {"technology_readiness_level": 4}, float(EffortCost.MEDIUM)),
            "process_automation_level":   ("Scalability Score", "Process automation level", {"process_automation_level": 0.60}, float(EffortCost.MEDIUM)),
        }
        for fname, (dim, crit, base_mut, effort) in _field_defaults.items():
            if getattr(profile, fname, None) is None and fname in missing_fields:
                actions.append(CandidateAction(
                    action_id=f"fill_missing_{fname}",
                    title=f"Complete '{crit}' — currently missing",
                    description=f"'{fname}' has no value. Complete in intake and upload evidence.",
                    effort=effort,
                    base_mutations=base_mut,
                    evidence_confirmations=[fname],
                    addresses_criteria=[crit],
                    resource_tags=[],
                    layer="universal",
                    base_assumptions=[f"'{fname}' can be assessed and documented."],
                ))

        return actions

    # ── Layer 2 (hand-written fallback templates) 

    def _layer2_sector(self, sector, profile, scores_by_name, weakest_criteria, stage, trl, anomalies):
        p = profile
        _get = lambda f, d=0: getattr(p, f, d) or d

        sector_templates: dict[str, list[CandidateAction]] = {
            Sector.SAAS: [
                CandidateAction(
                    action_id="saas_pilot_customers",
                    title="Launch pilot with 3 paying SaaS customers",
                    description="Structured 30-day pilot: 3 customers, documented conversion and churn feedback.",
                    effort=float(EffortCost.MEDIUM),
                    base_mutations={"paying_customers": _get("paying_customers") + 3,
                                    "revenue_model_clarity": min(_get("revenue_model_clarity") + 20, 100)},
                    evidence_confirmations=["paying_customers", "revenue_model_clarity"],
                    addresses_criteria=["Customer validation", "Revenue-model clarity"],
                    resource_tags=["mentor", "tool"],
                    layer="sector",
                    base_assumptions=["SaaS product is live and functional.", "3 target customers are reachable."],
                ),
                CandidateAction(
                    action_id="saas_funnel_analytics",
                    title="Instrument funnel analytics and document conversion rates",
                    description="Add event tracking. Document TOFU→BOFU conversion. Use data to set pricing.",
                    effort=float(EffortCost.LOW),
                    base_mutations={"competition_understanding": min(_get("competition_understanding") + 15, 100),
                                    "revenue_model_clarity": min(_get("revenue_model_clarity") + 10, 100)},
                    evidence_confirmations=["competition_understanding"],
                    addresses_criteria=["Competitive differentiation", "Revenue-model clarity"],
                    resource_tags=["tool"],
                    layer="sector",
                    base_assumptions=["Product is instrumented or can be within 2 days."],
                ),
                CandidateAction(
                    action_id="saas_pricing_experiment",
                    title="Run structured pricing experiment",
                    description="Test 2 price points on 10 prospects. Document WTP distribution and set tier.",
                    effort=float(EffortCost.LOW),
                    base_mutations={"revenue_model_clarity": min(_get("revenue_model_clarity") + 20, 100)},
                    evidence_confirmations=["revenue_model_clarity"],
                    addresses_criteria=["Revenue-model clarity"],
                    resource_tags=["learning"],
                    layer="sector",
                    base_assumptions=["10 qualified prospects are reachable for pricing conversations."],
                ),
            ],
            Sector.DEEPTECH: [
                CandidateAction(
                    action_id="deeptech_trl_validation",
                    title="Produce TRL validation report (lab-validated, TRL 4+)",
                    description="Document test protocols and results. Demonstrate technology under controlled conditions.",
                    effort=float(EffortCost.MEDIUM),
                    base_mutations={"technology_readiness_level": min((trl or 1) + 1, 9)},
                    evidence_confirmations=["technology_readiness_level"],
                    addresses_criteria=["Technological intensity (TRL)"],
                    resource_tags=["mentor", "program"],
                    layer="sector",
                    base_assumptions=[f"Lab or testing environment is accessible. Current TRL={trl or 'unknown'}."],
                ),
                CandidateAction(
                    action_id="deeptech_patent_strategy",
                    title="Develop patent strategy and file provisional patent",
                    description="Prior-art search + novelty documentation + provisional filing with INNORPI.",
                    effort=float(EffortCost.MEDIUM),
                    base_mutations={"ip_assets": ["provisional_patent"],
                                    "problem_novelty_score": min(_get("problem_novelty_score") + 20, 100)},
                    evidence_confirmations=["ip_assets", "problem_novelty_score"],
                    addresses_criteria=["IP / moat strength", "Problem novelty"],
                    resource_tags=["legal", "mentor"],
                    layer="sector",
                    base_assumptions=["Core innovation is defined enough to describe in a filing."],
                ),
                CandidateAction(
                    action_id="deeptech_prototype_testing",
                    title="Complete prototype testing in operational environment (TRL 7 target)",
                    description="Move from lab to operational environment. Document real-world performance.",
                    effort=float(EffortCost.HIGH),
                    base_mutations={"technology_readiness_level": min((trl or 1) + 2, 9),
                                    "problem_novelty_score": min(_get("problem_novelty_score") + 10, 100)},
                    evidence_confirmations=["technology_readiness_level"],
                    addresses_criteria=["Technological intensity (TRL)"],
                    resource_tags=["program", "mentor"],
                    layer="sector",
                    base_assumptions=["Operational environment partner is secured."],
                ),
            ],
            Sector.GREENTECH: [
                CandidateAction(
                    action_id="greentech_carbon_baseline",
                    title="Conduct 4-pillar environmental baseline audit",
                    description="Measure Climat/Air, Eau, Sols, Ressources. Set SDG 12 & 13 reduction targets.",
                    effort=float(EffortCost.LOW),
                    base_mutations={"climate_air_impact_score": min(_get("climate_air_impact_score") + 25, 100),
                                    "water_impact_score": min(_get("water_impact_score") + 20, 100),
                                    "resources_waste_score": min(_get("resources_waste_score") + 20, 100)},
                    evidence_confirmations=["climate_air_impact_score", "water_impact_score"],
                    addresses_criteria=["Climat / Air impact", "Water impact", "Resources & waste management"],
                    resource_tags=["program", "learning"],
                    layer="sector",
                    base_assumptions=["Utility bills and operational records are accessible."],
                ),
                CandidateAction(
                    action_id="greentech_impact_measurement",
                    title="Implement impact measurement framework",
                    description="Quarterly impact reporting aligned with SDG 12, 13, 15. Publish first impact report.",
                    effort=float(EffortCost.LOW),
                    base_mutations={"sdg_alignment_score": min(_get("sdg_alignment_score") + 30, 100),
                                    "soil_biodiversity_score": min(_get("soil_biodiversity_score") + 15, 100)},
                    evidence_confirmations=["sdg_alignment_score"],
                    addresses_criteria=["SDG alignment (PNUD/UN)", "Soil & biodiversity"],
                    resource_tags=["program"],
                    layer="sector",
                    base_assumptions=["Business activities are defined well enough to map to SDGs."],
                ),
            ],
            Sector.FINTECH: [
                CandidateAction(
                    action_id="fintech_regulatory_mapping",
                    title="Complete regulatory compliance mapping",
                    description="Map activities against BCT/APTBEF. Identify sandbox eligibility. Document gaps.",
                    effort=float(EffortCost.LOW),
                    base_mutations={"legal_compliance_score": min(_get("legal_compliance_score") + 25, 100)},
                    evidence_confirmations=["legal_compliance_score"],
                    addresses_criteria=["Legal / regulatory compliance"],
                    resource_tags=["legal", "program"],
                    layer="sector",
                    base_assumptions=["Legal advisor with FinTech expertise is available."],
                ),
                CandidateAction(
                    action_id="fintech_compliance_readiness",
                    title="Complete AML/KYC compliance documentation",
                    description="Implement AML/KYC policy and document compliance readiness for BCT review.",
                    effort=float(EffortCost.MEDIUM),
                    base_mutations={"legal_compliance_score": min(_get("legal_compliance_score") + 20, 100),
                                    "process_documentation_score": min(_get("process_documentation_score") + 15, 100)},
                    evidence_confirmations=["legal_compliance_score", "process_documentation_score"],
                    addresses_criteria=["Legal / regulatory compliance", "Process documentation"],
                    resource_tags=["legal"],
                    layer="sector",
                    base_assumptions=["AML/KYC framework template is available."],
                ),
            ],
            Sector.HEALTHTECH: [
                CandidateAction(
                    action_id="healthtech_regulatory_pathway",
                    title="Document clinical/regulatory pathway",
                    description="Map activities against applicable health-data and clinical regulations. Identify pilot-site eligibility.",
                    effort=float(EffortCost.MEDIUM),
                    base_mutations={"legal_compliance_score": min(_get("legal_compliance_score") + 25, 100)},
                    evidence_confirmations=["legal_compliance_score"],
                    addresses_criteria=["Legal / regulatory compliance"],
                    resource_tags=["legal", "program"],
                    layer="sector",
                    base_assumptions=["Regulatory advisor with health-sector expertise is available."],
                ),
            ],
        }

        return sector_templates.get(sector, [])

    # ── Layer 3 

    def _layer3_archetype(self, archetype_id, profile, scores_by_name, weakest_criteria, sector):
        _g = lambda f, d=0: getattr(profile, f, d) or d

        templates: dict[str, list[CandidateAction]] = {
            "RESEARCHER": [
                CandidateAction(
                    action_id="arch_researcher_commercial_partner",
                    title="Find commercial co-founder or BD partner (Researcher gap)",
                    description=(
                        "Innovation is strong but market engagement is weak — Researcher pattern. "
                        "Spend 3 weeks identifying and onboarding a commercial partner with an existing network."
                    ),
                    effort=float(EffortCost.HIGH),
                    base_mutations={"paying_customers": _g("paying_customers") + 2,
                                    "competition_understanding": min(_g("competition_understanding") + 20, 100)},
                    evidence_confirmations=["paying_customers"],
                    addresses_criteria=["Customer validation", "Competitive differentiation"],
                    resource_tags=["mentor", "program"],
                    layer="archetype",
                    base_assumptions=["RESEARCHER: commercial gap is the primary bottleneck.", "Active partner search is feasible."],
                ),
                CandidateAction(
                    action_id="arch_researcher_customer_sprint",
                    title="6-week customer discovery sprint (Researcher mode-shift)",
                    description=(
                        "No new features for 6 weeks. Run 15 customer interviews. "
                        "Document WTP, problem frequency, and alternative-awareness."
                    ),
                    effort=float(EffortCost.MEDIUM),
                    base_mutations={"documented_interviews": _g("documented_interviews") + 15,
                                    "market_validation_evidence": list(_g("market_validation_evidence", [])) + ["interview_transcripts"],
                                    "market_size_known": True},
                    evidence_confirmations=["documented_interviews", "market_validation_evidence"],
                    addresses_criteria=["Customer validation", "Market-share potential"],
                    resource_tags=["learning", "mentor"],
                    layer="archetype",
                    base_assumptions=["RESEARCHER: innovation pause for market discovery.", "15 target customers reachable."],
                ),
            ],
            "HUSTLER": [
                CandidateAction(
                    action_id="arch_hustler_ops_documentation",
                    title="Emergency operational documentation sprint (Hustler ops fix)",
                    description=(
                        "Operations cannot support sales momentum. "
                        "2-week sprint: document top 5 processes, assign owners, build financial model."
                    ),
                    effort=float(EffortCost.LOW),
                    base_mutations={"process_documentation_score": min(_g("process_documentation_score") + 30, 100),
                                    "financial_model_quality": min(_g("financial_model_quality") + 20, 100)},
                    evidence_confirmations=["process_documentation_score", "financial_model_quality"],
                    addresses_criteria=["Process documentation", "Financial model quality"],
                    resource_tags=["tool", "mentor"],
                    layer="archetype",
                    base_assumptions=["HUSTLER: operational lag is the primary bottleneck.", "Sales can pause 2 weeks."],
                ),
                CandidateAction(
                    action_id="arch_hustler_automate",
                    title="Automate fulfilment pipeline (Hustler ops fix)",
                    description="Identify 3 most manual fulfilment steps. Implement automation for current volume.",
                    effort=float(EffortCost.MEDIUM),
                    base_mutations={"process_automation_level": min(_g("process_automation_level", 0.0) + 0.25, 1.0),
                                    "infrastructure_readiness": min(_g("infrastructure_readiness") + 20, 100)},
                    evidence_confirmations=["process_automation_level"],
                    addresses_criteria=["Process automation level", "Infrastructure readiness"],
                    resource_tags=["tool"],
                    layer="archetype",
                    base_assumptions=["HUSTLER: automation is the highest-leverage operational fix."],
                ),
            ],
            "VISIONARY": [
                CandidateAction(
                    action_id="arch_visionary_single_feature_mvp",
                    title="Single-feature MVP in 30 days (Visionary focus constraint)",
                    description=(
                        "Pick exactly one feature. Build it. Ship to one paying customer in 30 days. "
                        "Visionary archetype suffers from scope creep — this action enforces focus."
                    ),
                    effort=float(EffortCost.HIGH),
                    base_mutations={"has_mvp": True,
                                    "paying_customers": _g("paying_customers") + 1},
                    evidence_confirmations=["has_mvp", "paying_customers"],
                    addresses_criteria=["MVP / product artifact", "Customer validation"],
                    resource_tags=["mentor", "incubator"],
                    layer="archetype",
                    base_assumptions=["VISIONARY: execution is the primary bottleneck.", "Scope is locked for 30 days."],
                ),
            ],
            "OPERATOR": [
                CandidateAction(
                    action_id="arch_operator_innovation_investment",
                    title="Allocate R&D budget and appoint innovation lead (Operator gap)",
                    description=(
                        "Operations are strong but differentiation is weak. "
                        "Allocate 15% of monthly budget to R&D. Define 3 innovation experiments."
                    ),
                    effort=float(EffortCost.HIGH),
                    base_mutations={"rd_investment_ratio": min(_g("rd_investment_ratio", 0.0) + 0.15, 1.0),
                                    "problem_novelty_score": min(_g("problem_novelty_score") + 15, 100)},
                    evidence_confirmations=["rd_investment_ratio"],
                    addresses_criteria=["R&D investment ratio", "Problem novelty"],
                    resource_tags=["mentor"],
                    layer="archetype",
                    base_assumptions=["OPERATOR: differentiation is the primary bottleneck.", "R&D budget exists."],
                ),
                CandidateAction(
                    action_id="arch_operator_competitive_analysis",
                    title="Deep competitive landscape analysis (Operator differentiation)",
                    description="Map 8 direct competitors: pricing, positioning, weakest segment.",
                    effort=float(EffortCost.LOW),
                    base_mutations={"competition_understanding": min(_g("competition_understanding") + 30, 100),
                                    "market_size_known": True},
                    evidence_confirmations=["competition_understanding"],
                    addresses_criteria=["Competitive differentiation", "Market-share potential"],
                    resource_tags=["learning"],
                    layer="archetype",
                    base_assumptions=["OPERATOR: market intelligence will unlock innovation direction."],
                ),
            ],
            "EVIDENCE_HOARDER": [
                CandidateAction(
                    action_id="arch_evidence_hoarder_upload_sprint",
                    title="2-hour artifact upload sprint (Evidence Hoarder unlock)",
                    description=(
                        "Set aside 2 hours. Upload every existing document: invoices, contracts, "
                        "reports, screenshots, test results."
                    ),
                    effort=float(EffortCost.TRIVIAL),
                    base_mutations={},
                    evidence_confirmations=[spec.field for criteria in _ALL_CRITERIA.values() for spec in criteria],
                    addresses_criteria=["All unverified criteria"],
                    resource_tags=[],
                    layer="archetype",
                    base_assumptions=["EVIDENCE_HOARDER: artifacts exist but are unuploaded."],
                ),
            ],
        }

        return templates.get(archetype_id, [])


# 5. OFFLINE AI-GENERATED KNOWLEDGE BASE LOADER

# This section loads pre-generated sector action libraries. The generation
# itself happens OFFLINE, build-time, via a separate script
# (scripts/generate_sector_kb.py, sketched at the bottom of this file) that
# calls Qwen3-32B once per sector to draft action templates, then a human
# reviews and commits the resulting JSON/YAML. 

# Expected file shape (data/knowledge_base/sector_actions/<sector>.json):
#   [
#     {
#       "title": "...",
#       "description": "...",
#       "mutation_hints": {"field_name": delta_or_value, ...},
#       "dependencies": ["other_action_id", ...],
#       "assumptions": ["...", "..."]
#     },
#     ...
#   ]
#
# mutation_hints are merged into CandidateAction.base_mutations verbatim —
# they are still just numbers/values, evaluated for real impact by
# CounterfactualEngine exactly like hand-written templates. The AI
# authored the IDEA and the COPY; the engine still verifies the EFFECT.

class SectorKnowledgeBase:
    """
    Loads offline AI-generated (or human-curated) action templates from
    JSON files on disk. Falls back silently to "no templates for this
    sector" if the file is missing — callers then use the hand-written
    Layer 2 templates instead. Never performs a network call.
    """

    def __init__(self, base_dir: str = "data/knowledge_base/sector_actions") -> None:
        self._base_dir = base_dir
        self._cache: dict[str, list[dict[str, Any]]] = {}

    def _load_raw(self, sector: str) -> list[dict[str, Any]]:
        if sector in self._cache:
            return self._cache[sector]
        path = f"{self._base_dir}/{sector}.json"
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, list):
                logger.warning("Sector KB file '%s' is not a list — ignoring.", path)
                data = []
        except FileNotFoundError:
            data = []
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load sector KB file '%s' (%s) — ignoring.", path, exc)
            data = []
        self._cache[sector] = data
        return data

    def actions_for_sector(self, sector: str, profile: Any) -> list[CandidateAction]:
        raw = self._load_raw(sector)
        actions: list[CandidateAction] = []
        for i, entry in enumerate(raw):
            try:
                action_id = f"kb_{sector}_{i:02d}"
                actions.append(CandidateAction(
                    action_id=action_id,
                    title=str(entry["title"]),
                    description=str(entry["description"]),
                    effort=float(entry.get("effort", float(EffortCost.MEDIUM))),
                    base_mutations=dict(entry.get("mutation_hints", {})),
                    evidence_confirmations=list(entry.get("mutation_hints", {}).keys()),
                    addresses_criteria=list(entry.get("addresses_criteria", [])),
                    resource_tags=list(entry.get("resource_tags", [])),
                    layer="sector",
                    base_assumptions=list(entry.get("assumptions", [])) + [
                        f"Sourced from offline AI-generated knowledge base (sector={sector})."
                    ],
                ))
            except (KeyError, ValueError, TypeError) as exc:
                logger.warning("Skipping malformed sector KB entry #%d for '%s': %s", i, sector, exc)
        return actions


# 6. RECOMMENDATION SEARCH ENGINE  (ranking ; sequencing
#    narrative = SEAM 2, LLM-assisted, ordering-within-graph only)

class RecommendationSearchEngine:
    """
    Generates, mutates, scores, and ranks CandidateActions by leverage.

        leverage = graph_weighted_readiness_gain / effort_cost

    Ranking by leverage is 100% deterministic (CounterfactualEngine +
    GraphWeightedReadinessEngine). After ranking, an OPTIONAL narrative
    pass (_sequence_recommendations, seam 2) asks the LLM to explain a
    coherent execution order — but the candidate set, the dependency
    edges (blocked_by), and the leverage numbers it must respect are all
    already fixed by the deterministic graph before the LLM is called.
    """

    _HORIZON_BY_EFFORT: dict[float, str] = {
        float(EffortCost.TRIVIAL):   "IMMEDIATE",
        float(EffortCost.LOW):       "IMMEDIATE",
        float(EffortCost.MEDIUM):    "SHORT_TERM",
        float(EffortCost.HIGH):      "MEDIUM_TERM",
        float(EffortCost.VERY_HIGH): "MEDIUM_TERM",
    }

    def __init__(
        self,
        cf_engine: CounterfactualEngine,
        mutation_engine: ContextualMutationEngine,
        graph_engine: "DimensionGraphEngine",
        readiness_engine: GraphWeightedReadinessEngine,
        knowledge_base: SectorKnowledgeBase | None = None,
        use_llm_narrative: bool = True,
    ) -> None:
        self._cf = cf_engine
        self._mut = mutation_engine
        self._graph = graph_engine
        self._readiness = readiness_engine
        self._kb = knowledge_base
        self._use_llm_narrative = use_llm_narrative

    def run(
        self,
        profile: Any,
        scores: Any,
        archetype_id: str,
        bottlenecks: list[BottleneckAnalysis],
        top_n: int = 10,
    ) -> tuple[list[CounterfactualResult], MilestoneRoadmap]:
        generator = SectorAwareActionGenerator(knowledge_base=self._kb)
        candidates = generator.generate(profile, scores, archetype_id, bottlenecks)

        sector = SectorStrategyRegistry.detect_sector(profile)
        stage = str(getattr(profile, "effective_stage", "IDEATION"))
        scores_by_name = {s.name: s for s in scores.scores}

        results: list[CounterfactualResult] = []
        action_map: dict[str, CandidateAction] = {}

        for action in candidates:
            try:
                mset = self._mut.build(action, profile, scores_by_name, archetype_id)
                result = self._cf.run(
                    mutation_set=mset,
                    action=action,
                    profile=profile,
                    scores_before=scores,
                    sector=sector,
                    stage=stage,
                    contextual_notes=[f"layer:{action.layer}", f"sector:{sector}"],
                )
                results.append(result)
                action_map[action.action_id] = action
            except Exception as exc:
                logger.warning("Action '%s' failed in counterfactual: %s", action.action_id, exc)

        # DECISION LAYER: ranking by leverage. Final and not subject to
        # LLM override.
        results.sort(key=lambda r: r.leverage, reverse=True)
        top = results[:top_n]

        readiness_report = self._readiness.compute(scores)
        roadmap = self._build_roadmap(top, action_map, readiness_report)

        # SEAM 2: narrative sequencing. see
        # _sequence_recommendations() docstring for the contract.
        if self._use_llm_narrative and top:
            sequence, generated_by = _sequence_recommendations(roadmap.milestones)
            roadmap.sequence_narrative = sequence
            roadmap.sequencing_generated_by = generated_by

        return top, roadmap

    def _build_roadmap(self, ranked, action_map, readiness_report):
        dep_edges = self._graph.get_dependency_edges()
        milestones: list[Milestone] = []

        for result in ranked:
            action = action_map.get(result.action_id)
            if not action:
                continue
            primary = max(result.score_deltas, key=lambda d: d.delta, default=None)
            addresses_score = primary.score_name if primary else "Unknown"
            horizon = self._HORIZON_BY_EFFORT.get(result.effort, "SHORT_TERM")
            blocked_by = [
                m.id for prereq, dep in dep_edges
                if addresses_score == dep
                for m in milestones if m.addresses_score == prereq
            ]

            # SEAM 4: per-milestone rationale (explanation only).
            rationale = _generate_milestone_rationale(action, result, blocked_by)

            milestones.append(Milestone(
                id=result.action_id,
                title=result.action_title,
                description=action.description,
                rationale=rationale,
                horizon=horizon,
                addresses_score=addresses_score,
                addresses_criteria=action.addresses_criteria,
                blocked_by=blocked_by,
                resource_tags=action.resource_tags,
                effort=result.effort,
                sector=result.sector,
                layer=action.layer,
                projected_score_deltas=result.score_deltas,
                overall_readiness_gain=result.overall_readiness_gain,
                leverage=result.leverage,
                mutation_set=result.mutation_set,
                contextual_notes=result.contextual_notes,
            ))

        critical_path = self._critical_path(milestones)
        overall_after = min(readiness_report.overall_readiness + sum(r.overall_readiness_gain for r in ranked), 100.0)

        return MilestoneRoadmap(
            milestones=milestones,
            critical_path=critical_path,
            overall_readiness_now=round(readiness_report.overall_readiness, 2),
            overall_readiness_after_all=round(overall_after, 2),
            readiness_report=readiness_report,
        )

    def _critical_path(self, milestones):
        visited: set[str] = set()
        path: list[str] = []
        queue = [m.id for m in milestones if not m.blocked_by]
        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node); path.append(node)
            queue.extend([m.id for m in milestones if node in m.blocked_by and m.id not in visited])
        return path


# SEAM 4: MILESTONE RATIONALE  ("explain why one action matters")

# Input: a single action + its already-computed CounterfactualResult +
# the dependency edges already assigned to it. Output: a short, grounded
# explanation string.

def _generate_milestone_rationale(
    action: CandidateAction,
    result: CounterfactualResult,
    blocked_by: list[str],
) -> str:
    """
    Seam 4. Produces Milestone.rationale: a short paragraph explaining why
    this specific action is worth doing, grounded in its actual computed
    leverage/gain/effort and its place in the dependency graph.

    Deterministic fallback (used when GROQ_API_KEY unset or call fails):
    a templated sentence built directly from the same numbers — lower
    prose quality, identical factual content, never fabricated.
    """
    prompt = f"""You write one-paragraph rationales for a startup-diagnostic roadmap tool.
You are NOT allowed to invent numbers — use only the figures given below.

ACTION: {action.title}
DESCRIPTION: {action.description}
EFFORT: {result.effort} founder-weeks
OVERALL READINESS GAIN: {result.overall_readiness_gain:+.2f} points (computed by re-running the scoring engine, not estimated)
LEVERAGE (gain / effort): {result.leverage:.3f}
SCORE DELTAS: {", ".join(f"{d.score_name} {d.delta:+.1f}" for d in result.score_deltas if abs(d.delta) > 0.05) or "negligible direct score movement"}
BLOCKED BY (must happen first): {", ".join(blocked_by) if blocked_by else "nothing — can start immediately"}
LAYER: {action.layer} (universal / sector-specific / archetype-specific)

Write valid JSON only:
{{"rationale": "<one paragraph, 2-4 sentences, citing the actual gain/leverage/effort numbers above, explaining WHY this action matters now>"}}"""

    parsed = _groq_chat_json(prompt, max_tokens=220, temperature=0.25)
    if parsed and isinstance(parsed.get("rationale"), str) and parsed["rationale"].strip():
        return parsed["rationale"].strip()

    # Deterministic fallback — same facts, template prose.
    blocker_clause = (
        f" It is currently blocked by: {', '.join(blocked_by)}."
        if blocked_by else " It can be started immediately."
    )
    return (
        f"This action is projected to raise overall readiness by "
        f"{result.overall_readiness_gain:+.2f} points for {result.effort:.1f} founder-weeks of "
        f"effort (leverage {result.leverage:.2f})." + blocker_clause
    )


# SEAM 2: RECOMMENDATION SEQUENCING  

def _sequence_recommendations(milestones: list[Milestone]) -> tuple[list[SequencedStep], str]:
    """
    Seam 2. Takes the already-ranked, already-leverage-scored, already
    dependency-graphed list of Milestones and asks the LLM to produce a
    human-readable execution narrative: which order to actually tackle
    them in, and why.

    HARD CONSTRAINT enforced both in the prompt and by post-validation:
    the LLM's proposed order must respect every Milestone.blocked_by edge
    that the deterministic dependency graph already computed. If the LLM
    output violates a dependency (sequences a blocked milestone before
    its blocker) we discard the LLM ordering for that milestone and fall
    back to the deterministic critical-path order. The LLM also cannot
    introduce or remove milestones — only sequence and narrate the exact
    set it was given.

    Returns (sequence, generated_by) where generated_by is either
    "llm:qwen3-32b" or "deterministic".
    """
    if not milestones:
        return [], "deterministic"

    id_to_milestone = {m.id: m for m in milestones}

    payload_milestones = [
        {
            "id": m.id,
            "title": m.title,
            "leverage": m.leverage,
            "overall_readiness_gain": m.overall_readiness_gain,
            "effort": m.effort,
            "blocked_by": m.blocked_by,
            "addresses_score": m.addresses_score,
            "layer": m.layer,
        }
        for m in milestones
    ]

    prompt = f"""You sequence an already-ranked list of startup roadmap milestones.
You may NOT change, add, or remove any milestone, and you may NOT reorder a
milestone ahead of anything listed in its own "blocked_by" — that dependency
is fixed by a separate deterministic engine and is non-negotiable.

Your only job: propose the most coherent execution order (respecting
blocked_by) and explain, for each milestone, why it sits where it does in
the sequence — referencing leverage, gain, effort, and dependencies as
given. Do not invent numbers not present below.

MILESTONES (JSON):
{json.dumps(payload_milestones, indent=2)}

Return ONLY valid JSON, a list in your proposed order:
[{{"id": "<milestone id from above>", "title": "<copy from input>", "rationale": "<1-2 sentences citing real numbers/dependencies>", "dependencies": ["<ids from blocked_by>"]}}, ...]
Include every milestone id exactly once."""

    parsed = _groq_chat_json(prompt, max_tokens=900, temperature=0.2)

    if parsed is not None:
        raw_list = parsed if isinstance(parsed, list) else parsed.get("sequence") or parsed.get("milestones")
        if isinstance(raw_list, list):
            validated = _validate_and_build_sequence(raw_list, id_to_milestone)
            if validated is not None:
                return validated, "llm:qwen3-32b"

    # Deterministic fallback: order by leverage descending, respecting
    # blocked_by via a simple topological pass 
    return _deterministic_sequence(milestones), "deterministic"


def _validate_and_build_sequence(
    raw_list: list[Any],
    id_to_milestone: dict[str, Milestone],
) -> list[SequencedStep] | None:
    """
    Validates the LLM's proposed sequence against the hard dependency
    constraint. Returns None (triggering deterministic fallback) if the
    LLM hallucinated an id, dropped a milestone, or proposed an order
    that violates blocked_by.
    """
    seen_ids: set[str] = set()
    steps: list[SequencedStep] = []
    position: dict[str, int] = {}

    for i, entry in enumerate(raw_list):
        if not isinstance(entry, dict):
            return None
        mid = entry.get("id")
        if mid not in id_to_milestone or mid in seen_ids:
            return None
        seen_ids.add(mid)
        position[mid] = i
        steps.append(SequencedStep(
            title=str(entry.get("title", id_to_milestone[mid].title)),
            rationale=str(entry.get("rationale", "")).strip(),
            dependencies=[d for d in entry.get("dependencies", []) if isinstance(d, str)],
            milestone_id=mid,
        ))

    if seen_ids != set(id_to_milestone.keys()):
        logger.warning("LLM sequence dropped or added milestones — falling back to deterministic order.")
        return None

    for mid, milestone in id_to_milestone.items():
        for dep in milestone.blocked_by:
            if dep in position and position[dep] > position[mid]:
                logger.warning(
                    "LLM sequence placed '%s' before its dependency '%s' — "
                    "falling back to deterministic order.", mid, dep,
                )
                return None

    return steps


def _deterministic_sequence(milestones: list[Milestone]) -> list[SequencedStep]:
    """Fallback ordering: topological by blocked_by, ties broken by leverage descending."""
    remaining = {m.id: m for m in milestones}
    placed: set[str] = set()
    ordered: list[Milestone] = []

    while remaining:
        ready = [m for m in remaining.values() if all(b in placed for b in m.blocked_by)]
        if not ready:
            # Cycle or unresolved dependency outside the given set — flush
            # remaining items by leverage to guarantee termination.
            ready = list(remaining.values())
        ready.sort(key=lambda m: m.leverage, reverse=True)
        chosen = ready[0]
        ordered.append(chosen)
        placed.add(chosen.id)
        del remaining[chosen.id]

    return [
        SequencedStep(
            title=m.title,
            rationale=(
                f"Selected by leverage ({m.leverage:.2f}) among milestones whose "
                f"dependencies are already satisfied."
            ),
            dependencies=list(m.blocked_by),
            milestone_id=m.id,
        )
        for m in ordered
    ]


# 7. DIMENSION GRAPH ENGINE  
class DimensionGraphEngine:
    _DIMENSION_DEPS: list[tuple[str, str, str]] = [
        ("Operational Score", "Market Score",
         "Market validation requires a product artifact. Without MVP, paying-customer evidence is structurally weak."),
        ("Operational Score", "Scalability Score",
         "Scalability without operational foundation is premature."),
        ("Market Score", "Scalability Score",
         "High scalability with low market signal wastes capacity."),
        ("Innovation Score", "Market Score",
         "High TRL without market validation creates technology-push risk."),
    ]

    def __init__(self, scores: Any, profile: Any) -> None:
        self._by_name = {s.name: s for s in scores.scores}
        self._profile = profile
        self._nodes: dict[str, GraphNode] = {}
        for dim, criteria in _ALL_CRITERIA.items():
            s = self._by_name.get(dim)
            if not s:
                continue
            w = _READINESS_WEIGHTS.get(dim, 0.2)
            self._nodes[dim] = GraphNode(dim, "dimension", dim, s.value, w, False,
                                          max(0.0, 100.0 - s.value) * w)
            for spec in criteria:
                sub = next((ss for ss in s.sub_scores if ss.name == spec.name), None)
                if sub is None:
                    continue
                self._nodes[f"{dim}::{spec.name}"] = GraphNode(
                    f"{dim}::{spec.name}", "criterion", dim, sub.value,
                    spec.weight, spec.fundamental,
                    spec.weight * (1.0 - sub.value / 100.0) * 100.0 * w,
                )

    def get_bottlenecks(self) -> list[BottleneckAnalysis]:
        analyses: list[BottleneckAnalysis] = []
        for src, tgt, expl in self._DIMENSION_DEPS:
            sn = self._nodes.get(src)
            tn = self._nodes.get(tgt)
            if not sn or not tn or sn.current_value >= 65.0 or tn.marginal_gain_if_maxed < 2.0:
                continue
            gap = max(0.0, 65.0 - sn.current_value)
            blocked = tn.marginal_gain_if_maxed * (gap / 65.0)
            analyses.append(BottleneckAnalysis(
                bottleneck_node_id=src,
                bottleneck_type="dimension",
                blocked_potential=round(blocked, 2),
                explanation=(
                    f"'{src}' is at {sn.current_value:.0f}/100 and blocks '{tgt}' "
                    f"({tn.current_value:.0f}/100). {expl} "
                    f"Prioritising '{src}' unblocks {blocked:.1f} readiness pts."
                ),
                improving_others_first_explanation=(
                    f"Improving '{tgt}' while '{src}' stays at {sn.current_value:.0f} yields "
                    f"only {tn.marginal_gain_if_maxed:.1f} readiness pts. {expl}"
                ),
            ))
        for dim, s in self._by_name.items():
            for spec in _ALL_CRITERIA.get(dim, []):
                if not spec.fundamental:
                    continue
                sub = next((ss for ss in s.sub_scores if ss.name == spec.name), None)
                if not sub or sub.value >= 50.0:
                    continue
                penalty = s.value * LAMBDA_DEFAULT * (1.0 - sub.value / 100.0)
                w = _READINESS_WEIGHTS.get(dim, 0.2)
                analyses.append(BottleneckAnalysis(
                    bottleneck_node_id=f"{dim}::{spec.name}",
                    bottleneck_type="fundamental_criterion",
                    blocked_potential=round(penalty * w, 2),
                    explanation=(
                        f"'{spec.name}' in {dim} at {sub.value:.0f}/100 (fundamental, w={spec.weight:.0%}). "
                        f"λ-penalty suppresses {dim} by ~{penalty:.1f} pts. "
                        "Raising above 60 eliminates most of the penalty."
                    ),
                    improving_others_first_explanation=(
                        f"Other sub-criteria in {dim} are dampened while '{spec.name}' "
                        f"stays at {sub.value:.0f} — λ-penalty applies regardless."
                    ),
                ))
        analyses.sort(key=lambda a: a.blocked_potential, reverse=True)
        return analyses

    def get_dependency_edges(self) -> list[tuple[str, str]]:
        return [(s, t) for s, t, _ in self._DIMENSION_DEPS
                if self._nodes.get(s, GraphNode("", "", None, 100.0, 0.0, False, 0.0)).current_value < 65.0]


# ===========================================================================
# 8. CONTRIBUTION ANALYSER  (DECISION LAYER — unchanged from v3)
# ===========================================================================

class ContributionAnalyser:
    def analyse(self, score: Any, profile: Any, dim_name: str) -> ScoreDecomposition:
        criteria = _ALL_CRITERIA.get(dim_name, [])
        contribs: list[CriterionContribution] = []
        c_base = 0.0
        x_min_f = 1.0
        weakest_f: str | None = None
        ev_cost_total = 0.0

        for spec in criteria:
            sub = next((ss for ss in score.sub_scores if ss.name == spec.name), None)
            raw = (sub.value / 100.0) if sub else 0.0
            contrib = spec.weight * raw
            c_base += contrib
            ledger = getattr(profile, "evidence_ledger", {}) or {}
            entry = ledger.get(spec.field)
            ev_status = str(entry.status) if entry else ("unverified" if raw > 0 else "absent")
            e_j = 1.0 if ev_status == "confirmed" else 0.0
            ev_cost = spec.weight * (1.0 - e_j)
            ev_cost_total += ev_cost
            if spec.fundamental and sub and raw < x_min_f:
                x_min_f = raw
                weakest_f = spec.name
            contribs.append(CriterionContribution(
                criterion_name=spec.name, weight=spec.weight, raw_value=raw,
                weighted_contribution=round(contrib * 100, 2), is_fundamental=spec.fundamental,
                lambda_penalty_exposure=round(spec.weight * LAMBDA_DEFAULT * (1.0 - raw), 4) if spec.fundamental else 0.0,
                evidence_status=ev_status, evidence_cost=round(ev_cost, 4),
                is_weakest_fundamental=(spec.name == weakest_f),
            ))

        lambda_cost = max(0.0, c_base * 100.0 - c_base * (1.0 - LAMBDA_DEFAULT * (1.0 - x_min_f)) * 100.0)
        causes: list[tuple[float, str]] = []
        if lambda_cost > 3.0 and weakest_f:
            causes.append((lambda_cost, f"λ-penalty: '{weakest_f}' at {x_min_f*100:.0f}/100 suppresses composite by {lambda_cost:.1f} pts."))
        for c in contribs:
            gap = (c.weight - c.weighted_contribution / 100.0) * 100.0
            if gap > 2.0:
                s = f"'{c.criterion_name}' contributes {c.weighted_contribution:.1f}/{c.weight*100:.0f} pts (raw={c.raw_value*100:.0f}, w={c.weight:.0%})."
                if c.evidence_status != "confirmed":
                    s += f" Evidence='{c.evidence_status}' → confirming adds {c.evidence_cost*100:.1f}% confidence."
                causes.append((gap, s))
        for a in score.anomalies:
            causes.append((5.0, f"Anomaly '{a}' active — forces evidence=0 for involved criteria."))
        for m in score.missing_criteria:
            causes.append((8.0, f"'{m}' has no data — contributes 0 to composite and confidence."))
        causes.sort(key=lambda x: x[0], reverse=True)

        return ScoreDecomposition(
            score_name=dim_name, composite_value=round(score.value, 2),
            c_base=round(c_base * 100, 2), lambda_penalty_cost=round(lambda_cost, 2),
            lambda_penalty_fraction=round(lambda_cost / max(c_base * 100, 1.0), 3),
            weakest_fundamental_criterion=weakest_f,
            weakest_fundamental_value=round(x_min_f * 100, 2) if weakest_f else None,
            criterion_contributions=sorted(contribs, key=lambda c: c.weighted_contribution, reverse=True),
            anomaly_penalties=score.anomalies, anomaly_confidence_cost=0.0,
            top_reduction_causes=[c for _, c in causes[:5]],
            missing_evidence_cost=round(ev_cost_total, 4),
            confidence_value=round(score.confidence, 3),
        )


# 9. ARCHETYPE ENGINE 

class ArchetypeEngine:
    """
    Detection is fully deterministic: 12 signals over actual score/
    confidence/anomaly values, aggregated by weighted vote. This class
    NEVER calls the LLM. The narrative text (pattern_description,
    strategic_recommendation) is produced afterward by
    _generate_archetype_narrative() (seam 1), which receives the
    detection output as its only input.
    """

    def detect(self, scores: Any, profile: Any) -> FounderArchetype:
        bn = {s.name: s for s in scores.scores}
        v = lambda n: bn[n].value if n in bn else 0.0
        c = lambda n: bn[n].confidence if n in bn else 0.0
        miss = lambda n: len(bn[n].missing_criteria) if n in bn else 5
        all_anom = [a for s in scores.scores for a in s.anomalies]
        avg_conf = sum(c(s.name) for s in scores.scores) / max(len(scores.scores), 1)
        total_miss = sum(miss(s.name) for s in scores.scores)
        avg_v = sum(v(s.name) for s in scores.scores) / max(len(scores.scores), 1)

        sigs: list[tuple[str, float, str, str]] = []
        if v("Innovation Score") > v("Market Score") + 25:
            sigs.append(("RESEARCHER", 2.0, "Innovation >> Market", f"Inn={v('Innovation Score'):.0f}, Mkt={v('Market Score'):.0f}"))
        if v("Innovation Score") >= 60 and v("Market Score") < 45:
            sigs.append(("RESEARCHER", 1.5, "Strong innovation, no market validation", f"Inn={v('Innovation Score'):.0f}, Mkt={v('Market Score'):.0f}"))
        if "high_innovation_claim_no_ip" in all_anom:
            sigs.append(("RESEARCHER", 1.0, "Innovation claimed without IP", "anomaly:high_innovation_claim_no_ip"))
        if v("Market Score") > v("Operational Score") + 25:
            sigs.append(("HUSTLER", 2.0, "Market >> Operational", f"Mkt={v('Market Score'):.0f}, Ops={v('Operational Score'):.0f}"))
        if v("Market Score") >= 60 and v("Operational Score") < 45:
            sigs.append(("HUSTLER", 1.5, "Traction without operational foundation", f"Mkt={v('Market Score'):.0f}, Ops={v('Operational Score'):.0f}"))
        if "revenue_without_mvp_artifact" in all_anom:
            sigs.append(("HUSTLER", 1.8, "Revenue without MVP", "anomaly:revenue_without_mvp_artifact"))
        if v("Innovation Score") >= 60 and v("Operational Score") < 40 and v("Scalability Score") < 40:
            sigs.append(("VISIONARY", 2.5, "High innovation, low execution", f"Inn={v('Innovation Score'):.0f}, Ops={v('Operational Score'):.0f}"))
        if v("Operational Score") > v("Innovation Score") + 25 and v("Operational Score") > v("Market Score") + 25:
            sigs.append(("OPERATOR", 2.0, "Operational dominance over innovation+market", f"Ops={v('Operational Score'):.0f}"))
        if avg_conf < 0.3 and avg_v >= 50:
            sigs.append(("EVIDENCE_HOARDER", 2.0, "Reasonable scores, near-zero confirmed evidence", f"avg_v={avg_v:.0f}, avg_conf={avg_conf:.2f}"))
        if avg_v < 40:
            sigs.append(("EARLY_STAGE", 3.0, "All dimensions below 40", f"avg={avg_v:.0f}"))
        if total_miss >= 15:
            sigs.append(("EARLY_STAGE", 2.0, "Profile largely unanswered", f"missing={total_miss}"))
        if not sigs or max(s[1] for s in sigs) < 1.5:
            sigs.append(("BALANCED", 1.0, "No dominant pattern", f"avg={avg_v:.0f}"))

        weights: dict[str, float] = {}
        arch_sigs: dict[str, list[ArchetypeSignal]] = {}
        for aid, w, desc, evid in sigs:
            weights[aid] = weights.get(aid, 0.0) + w
            arch_sigs.setdefault(aid, []).append(
                ArchetypeSignal(f"{aid}_{len(arch_sigs.get(aid, []))}", desc, evid)
            )

        total_weight = sum(weights.values()) or 1.0
        ranked_archetypes = sorted(weights.items(), key=lambda kv: kv[1], reverse=True)
        best_id, best_weight = ranked_archetypes[0]
        secondary_id = ranked_archetypes[1][0] if len(ranked_archetypes) > 1 else None
        confidence = round(best_weight / total_weight, 3)

        return self._build(
            best_id, secondary_id, confidence, avg_conf,
            arch_sigs.get(best_id, []), scores, profile,
        )

    _LABELS: dict[str, str] = {
        "RESEARCHER": "The Researcher",
        "HUSTLER": "The Hustler",
        "VISIONARY": "The Visionary",
        "OPERATOR": "The Operator",
        "EVIDENCE_HOARDER": "The Evidence Hoarder",
        "EARLY_STAGE": "The Early-Stage Builder",
        "BALANCED": "The Balanced Builder",
    }

    # Deterministic, signal-derived next-stage gates. These are factual
    # thresholds (what unlocks the next stage)
    _NEXT_GATES: dict[str, str] = {
        "RESEARCHER": "Market gate: paying_customers ≥ 5 with uploaded evidence.",
        "HUSTLER": "Ops gate: has_mvp=True + process_documentation_score ≥ 60.",
        "VISIONARY": "MVP gate: has_mvp=True with one documented transaction.",
        "OPERATOR": "Innovation gate: TRL ≥ 4 with filed IP.",
        "EVIDENCE_HOARDER": "Evidence gate: avg_confidence ≥ 0.50.",
        "EARLY_STAGE": "Foundation gate: 3 dimensions ≥ 40.",
        "BALANCED": "Stage gate: confirm top-3 unverified criteria by weight.",
    }
    _CO_FOUNDER_FIT: dict[str, str] = {
        "RESEARCHER": "Commercial co-founder or BD lead with existing sector network.",
        "HUSTLER": "COO or VP Operations — builds systems, not doors.",
        "VISIONARY": "Technical co-founder with proven shipping track record.",
        "OPERATOR": "Product or innovation lead who translates market insight to features.",
        "EVIDENCE_HOARDER": "Not a co-founder issue — personal discipline ritual.",
        "EARLY_STAGE": "Generalist covering tech and commercial gaps simultaneously.",
        "BALANCED": "Domain expert in primary sector.",
    }

    def _build(
        self,
        aid: str,
        secondary_id: str | None,
        confidence: float,
        evidence_quality: float,
        sigs: list[ArchetypeSignal],
        scores: Any,
        profile: Any,
    ) -> FounderArchetype:
        weakest = sorted(scores.scores, key=lambda s: s.value)[:2]
        weakest_dims = [s.name for s in weakest]

        pattern_description, strategic_recommendation, narrative_source = _generate_archetype_narrative(
            archetype_id=aid,
            label=self._LABELS.get(aid, aid),
            scores=scores,
            confidence=confidence,
            evidence_quality=evidence_quality,
            weakest_dimensions=weakest_dims,
            signals=sigs,
        )

        return FounderArchetype(
            archetype_id=aid,
            label=self._LABELS.get(aid, aid),
            secondary_archetype_id=secondary_id,
            confidence=confidence,
            evidence_quality=round(evidence_quality, 3),
            pattern_description=pattern_description,
            triggering_signals=sigs,
            strategic_recommendation=strategic_recommendation,
            co_founder_fit=self._CO_FOUNDER_FIT.get(aid, "Generalist co-founder."),
            next_stage_gate=self._NEXT_GATES.get(aid, "Re-run diagnostic after next milestone."),
            narrative_generated_by=narrative_source,
        )


# ===========================================================================
# SEAM 1: ARCHETYPE NARRATIVE
# ===========================================================================

def _generate_archetype_narrative(
    archetype_id: str,
    label: str,
    scores: Any,
    confidence: float,
    evidence_quality: float,
    weakest_dimensions: list[str],
    signals: list[ArchetypeSignal],
) -> tuple[str, str, str]:
    """
    Seam 1. Input is exclusively the deterministic detector's output —
    archetype id/label, vote confidence, evidence quality, the weakest
    dimensions, and the supporting signals with their concrete evidence
    strings (e.g. "Inn=72, Mkt=38"). The LLM may only rephrase and
    explain these; it must not introduce a different pattern than the
    one already detected, and must not cite a number that is not present
    in the input below.

    Returns (pattern_description, strategic_recommendation, generated_by).
    """
    score_summary = ", ".join(f"{s.name}={s.value:.0f}/100 (conf={s.confidence:.0%})" for s in scores.scores)
    signal_summary = "\n".join(f"  - {sig.description}: {sig.evidence}" for sig in signals) or "  - (no specific signals recorded)"

    prompt = f"""You write grounded behavioural-pattern descriptions for a startup diagnostic tool.
Archetype already detected by a deterministic rule engine: "{label}" ({archetype_id}).
Detection confidence (vote share): {confidence:.0%}. Evidence quality (avg confirmed-evidence score): {evidence_quality:.0%}.

ACTUAL SCORES: {score_summary}
WEAKEST DIMENSIONS: {', '.join(weakest_dimensions)}
SUPPORTING SIGNALS THAT TRIGGERED THIS ARCHETYPE:
{signal_summary}

Write exactly two things, grounded ONLY in the numbers and signals above
— do not use generic startup-advice language, do not invent facts, do
not contradict the detected archetype:
1. pattern_description: 2-3 sentences explaining WHY this specific founder
   was classified this way, citing the actual signal evidence.
2. strategic_recommendation: 2-3 sentences of concrete next action,
   referencing the weakest dimensions by name.

Return ONLY valid JSON:
{{"pattern_description": "...", "strategic_recommendation": "..."}}"""

    parsed = _groq_chat_json(prompt, max_tokens=400, temperature=0.3)
    if (
        parsed
        and isinstance(parsed.get("pattern_description"), str)
        and isinstance(parsed.get("strategic_recommendation"), str)
        and parsed["pattern_description"].strip()
        and parsed["strategic_recommendation"].strip()
    ):
        return parsed["pattern_description"].strip(), parsed["strategic_recommendation"].strip(), "llm:qwen3-32b"

    # Deterministic fallback — built only from the same signal data, no
    # fixed per-archetype persona paragraph (the v3 hardcoded personas
    # are intentionally NOT reproduced here).
    evidence_clause = "; ".join(f"{sig.description} ({sig.evidence})" for sig in signals[:2]) or "no single dominant signal"
    pattern_description = (
        f"Classified as '{label}' with {confidence:.0%} signal agreement, driven by: {evidence_clause}. "
        f"Weakest dimensions are {', '.join(weakest_dimensions)}, with overall evidence quality at {evidence_quality:.0%}."
    )
    strategic_recommendation = (
        f"Prioritise improving {weakest_dimensions[0] if weakest_dimensions else 'the weakest dimension'} "
        f"before investing further in stronger dimensions; this profile's confirmed-evidence rate ({evidence_quality:.0%}) "
        "suggests uploading supporting artifacts is also a high-leverage, low-effort parallel action."
    )
    return pattern_description, strategic_recommendation, "deterministic"


# 10. RESOURCE RETRIEVER 
class ResourceRetriever:
    _FALLBACK: list[dict[str, Any]] = [
        dict(category="FUNDING",  name="BFPME Startup Line",         description="Public bank financing up to 300 KTND.",     url="https://www.bfpme.com.tn",        score_focus="Market Score",      eligibility_conditions=["has_mvp", "paying_customers"]),
        dict(category="FUNDING",  name="Smart Capital Tunisia",       description="Seed fund for tech startups.",              url="https://www.smartcapital.com.tn", score_focus="Innovation Score",  eligibility_conditions=["technology_readiness_level", "ip_assets"]),
        dict(category="FUNDING",  name="UNDP Acceleration",           description="SDG-aligned impact startup cohort.",        url="https://www.undp.org/tunisia",    score_focus="Green Score",       eligibility_conditions=["sdg_alignment_score"]),
        dict(category="MENTOR",   name="APII Startup Advisory",       description="Free 4-session advisory programme.",        url="https://www.apii.com.tn",         score_focus="Innovation Score",  eligibility_conditions=[]),
        dict(category="MENTOR",   name="Flat6Labs Tunis",             description="Regional accelerator + seed.",              url="https://flat6labs.com/tunis",     score_focus="Market Score",      eligibility_conditions=["has_mvp"]),
        dict(category="TOOL",     name="Notion",                      description="Process documentation platform.",           url="https://notion.so",               score_focus="Operational Score", eligibility_conditions=[]),
        dict(category="LEARNING", name="Steve Blank — Customer Discovery", description="Lean Startup customer discovery.",    url="https://www.coursera.org",        score_focus="Market Score",      eligibility_conditions=[]),
        dict(category="LEARNING", name="MIT OCW — Tech Entrepreneurship",  description="TRL, IP, commercialisation.",          url="https://ocw.mit.edu",             score_focus="Innovation Score",  eligibility_conditions=[]),
        dict(category="PROGRAM",  name="Startup Act Tunisia",         description="Tax benefits, CNSS relief, bank access.",   url="https://startup.gov.tn",          score_focus="Operational Score", eligibility_conditions=["legal_compliance_score"]),
        dict(category="LEGAL",    name="INNORPI IP Filing",           description="Provisional patent filing assistance.",     url="https://www.innorpi.tn",          score_focus="Innovation Score",  eligibility_conditions=[]),
    ]

    def __init__(self, resource_service: Any = None) -> None:
        self._svc = resource_service

    def retrieve(self, profile: Any, scores: Any, top_n: int = 8) -> list[ResourceRecommendation]:
        if self._svc is not None:
            try:
                return self._from_service(profile, scores, top_n)
            except Exception as exc:
                logger.warning("resource_service failed (%s) — fallback.", exc)
        return self._from_fallback(profile, scores, top_n)

    def _from_service(self, profile, scores, top_n):
        ctx = {
            "sector": getattr(profile, "sector", "technology"),
            "sub_sector": getattr(profile, "sub_sector", None),
            "country": str(getattr(profile, "country", "TN")),
            "maturity_stage": str(getattr(profile, "effective_stage", "IDEATION")),
            "trl": getattr(profile, "technology_readiness_level", None),
            "sdg_alignment": getattr(profile, "sdg_alignment_score", None),
            "weak_criteria": [sub.name for s in scores.scores for sub in s.sub_scores if sub.value < 50][:6],
            "anomalies": [a for s in scores.scores for a in s.anomalies],
        }
        raw = self._svc.retrieve(query_context=ctx, top_n=top_n)
        return [ResourceRecommendation(
            category=getattr(r, "type", "UNKNOWN").upper(), name=getattr(r, "name", ""),
            description=getattr(r, "name", ""), url=getattr(r, "source_url", ""),
            relevance_explanation=" | ".join(getattr(r, "matched_reasons", [])),
            score_focus="", eligibility_met=True,
            similarity_score=getattr(r, "relevance_score", 0.5), priority=i + 1,
        ) for i, r in enumerate(raw)]

    def _from_fallback(self, profile, scores, top_n):
        weak_dims = {s.name for s in scores.scores if s.value < 65}
        scored = []
        for res in self._FALLBACK:
            met = sum(1 for c in res["eligibility_conditions"] if _is_field_truthy(profile, c))
            total = len(res["eligibility_conditions"])
            rel = (0.6 if res["score_focus"] in weak_dims else 0.3) + (met / max(total, 1)) * 0.4
            scored.append((rel, res))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [ResourceRecommendation(
            category=res["category"], name=res["name"], description=res["description"], url=res["url"],
            relevance_explanation=f"Addresses '{res['score_focus']}'" + (" (weak)" if res["score_focus"] in weak_dims else ""),
            score_focus=res["score_focus"],
            eligibility_met=any(_is_field_truthy(profile, c) for c in res["eligibility_conditions"]) or not res["eligibility_conditions"],
            similarity_score=round(score, 3), priority=i + 1,
        ) for i, (score, res) in enumerate(scored[:top_n])]


def _is_field_truthy(profile: Any, field_name: str) -> bool:
    val = getattr(profile, field_name, None)
    if val is None: return False
    if isinstance(val, list): return len(val) > 0
    if isinstance(val, bool): return val
    if isinstance(val, (int, float)): return val > 0
    return bool(val)


# 11. CONFIDENCE SIGNALS  

def _generate_confidence_signals(scores: Any, profile: Any) -> list[ConfidenceSignal]:
    _UPLOADS: dict[str, str] = {
        "market_size_known": "Upload TAM/SAM/SOM analysis document.",
        "paying_customers": "Upload customer invoices, contracts, or payment records.",
        "market_validation_evidence": "Upload interview transcripts or survey results.",
        "revenue_model_clarity": "Upload unit economics one-pager.",
        "competition_understanding": "Upload competitive landscape analysis.",
        "process_automation_level": "Upload automation assessment or tool audit.",
        "tech_stack_scalability": "Upload architecture diagram with load capacity data.",
        "technology_readiness_level": "Upload TRL validation report.",
        "problem_novelty_score": "Upload prior-art search results.",
        "ip_assets": "Upload patent filing receipt or trade-secret declaration.",
        "rd_investment_ratio": "Upload R&D budget allocation document.",
        "has_mvp": "Upload product demo, screenshot, or deployment link.",
        "process_documentation_score": "Upload process runbooks or SOPs.",
        "financial_model_quality": "Upload 18-month financial model spreadsheet.",
        "legal_compliance_score": "Upload RNE certificate, CNSS, and DGI filings.",
        "climate_air_impact_score": "Upload energy consumption baseline report.",
        "water_impact_score": "Upload water usage and treatment documentation.",
        "sdg_alignment_score": "Upload SDG alignment statement.",
    }
    signals: list[ConfidenceSignal] = []
    seen: set[str] = set()
    for score in scores.scores:
        if score.value <= 30 and score.confidence >= 0.30:
            continue
        for spec in _ALL_CRITERIA.get(score.name, []):
            ledger = getattr(profile, "evidence_ledger", {}) or {}
            entry = ledger.get(spec.field)
            status = str(entry.status) if entry else "absent"
            if status == "confirmed" or score.name in seen:
                continue
            if score.value < 45 and score.confidence >= 0.30:
                continue
            signals.append(ConfidenceSignal(
                score_name=score.name, current_score=round(score.value, 1),
                current_confidence=round(score.confidence, 3),
                criterion_name=spec.name, criterion_weight=spec.weight,
                upload_action=_UPLOADS.get(spec.field, f"Upload confirmation for '{spec.name}'."),
                expected_confidence_gain=round(spec.weight, 4),
            ))
            seen.add(score.name)
    signals.sort(key=lambda s: s.expected_confidence_gain, reverse=True)
    return signals


# SEAM 3: SWOT 

def _build_swot_prompt(
    profile: Any,
    scores: Any,
    archetype: FounderArchetype,
    decompositions: list[ScoreDecomposition],
    readiness_report: ReadinessReport,
    bottlenecks: list[BottleneckAnalysis],
) -> str:
    """
    Seam 3. The prompt is the only place the LLM ever sees raw profile
    context; it is never allowed to produce anything but the four SWOT
    lists. Unlike v3, this now feeds in the actual ReadinessReport
    (overall readiness, bottleneck cost, dependency multipliers) and the
    actual BottleneckAnalysis list, so "Threats" can name a real
    structural bottleneck instead of generic competitive boilerplate.
    """
    score_lines = "\n".join(
        f"  {s.name}: value={s.value:.0f}/100, confidence={s.confidence:.0%}, anomalies={s.anomalies}"
        for s in scores.scores
    )
    decomp_lines = "\n".join(
        f"  {d.score_name}: λ_cost={d.lambda_penalty_cost:.1f}pts, "
        f"weakest_fundamental='{d.weakest_fundamental_criterion}' at {(d.weakest_fundamental_value or 0):.0f}/100, "
        f"top_causes={d.top_reduction_causes[:2]}"
        for d in decompositions
    )
    readiness_lines = (
        f"  overall_readiness={readiness_report.overall_readiness:.1f}/100\n"
        f"  readiness_without_dependency_penalty={readiness_report.readiness_without_penalty:.1f}/100\n"
        f"  bottleneck_cost={readiness_report.bottleneck_cost:.1f} pts (gap caused by dependency chain, not raw scores)\n"
        f"  weakest_link_floor={readiness_report.weakest_link_floor:.1f}\n"
        + "\n".join(
            f"  {c.dimension}: effective={c.effective_score:.1f} (dependency_multiplier={c.dependency_multiplier:.2f})"
            for c in readiness_report.contributions
        )
    )
    bottleneck_lines = "\n".join(
        f"  [{b.bottleneck_type}] {b.bottleneck_node_id}: blocks {b.blocked_potential:.1f} readiness pts — {b.explanation}"
        for b in bottlenecks[:4]
    ) or "  (no material bottlenecks detected)"

    return f"""You are an expert startup advisor providing SWOT analysis for a Tunisian entrepreneur.
You must ground every bullet in the data below. Do not invent facts. Do not use generic SWOT boilerplate.

PROFILE:
  Sector: {getattr(profile, 'sector', 'technology')}
  Stage: {getattr(profile, 'effective_stage', 'IDEATION')}
  Archetype: {archetype.label} (detection confidence {archetype.confidence:.0%}) — {archetype.pattern_description}

SCORES:
{score_lines}

SCORE DECOMPOSITION (what is actually suppressing each score):
{decomp_lines}

READINESS REPORT (graph-weighted, dependency-aware overall readiness):
{readiness_lines}

STRUCTURAL BOTTLENECKS (from the dependency graph — use these for Threats, not generic competition language):
{bottleneck_lines}

RULES:
- Strengths: derive ONLY from scores ≥ 60, confirmed evidence, or high dependency_multiplier (≥0.85). Name the specific dimension/criterion.
- Weaknesses: derive ONLY from actual score gaps, missing criteria, active anomalies, or low dependency_multiplier. Name them explicitly with their numbers.
- Opportunities: Tunisia-specific programs (BFPME, Smart Capital, Startup Act, UNDP/GEWEET) relevant to the current stage and weakest dimension.
- Threats: MUST be derived from the structural bottlenecks listed above (cite the blocked readiness points) or from active anomalies — not generic "competition" statements unless no bottleneck data exists.
- Each quadrant: exactly 3 bullet points. Factual language, cite numbers where natural.

Return ONLY valid JSON. No markdown. No preamble. No trailing text:
{{"strengths":["...","...","..."],"weaknesses":["...","...","..."],"opportunities":["...","...","..."],"threats":["...","...","..."]}}"""


async def _call_groq_swot_async(prompt: str) -> SWOTAnalysis:
    parsed = await _groq_chat_json_async(prompt, max_tokens=700, temperature=0.3)
    if parsed and all(k in parsed for k in ("strengths", "weaknesses", "opportunities", "threats")):
        return SWOTAnalysis(
            strengths=list(parsed.get("strengths", [])),
            weaknesses=list(parsed.get("weaknesses", [])),
            opportunities=list(parsed.get("opportunities", [])),
            threats=list(parsed.get("threats", [])),
            generated_by="llm:qwen3-32b",
        )
    return _swot_deterministic()


def _swot_deterministic() -> SWOTAnalysis:
    """
    Fallback only — used when GROQ_API_KEY is unset or the call fails.
    Intentionally generic since it has no profile-specific data to draw
    on without the LLM; callers should prefer the LLM path whenever
    possible for this seam.
    """
    return SWOTAnalysis(
        strengths=["Operating in Tunisia's growing tech ecosystem with APII support available.",
                   "Startup Act Tunisia provides structural tax and social security advantages.",
                   "Early-stage profile — foundational elements are in progress."],
        weaknesses=["Evidence ledger partially unverified — confidence below 50% across dimensions.",
                    "Missing criteria across multiple dimensions reducing composite scores.",
                    "No confirmed IP or market validation documents uploaded yet."],
        opportunities=["BFPME and Smart Capital financing available for market-validated startups.",
                       "UNDP/GEWEET acceleration programmes seeking SDG-aligned ventures.",
                       "North Africa digital market growing at 18% CAGR."],
        threats=["Structural bottleneck data unavailable — recommend re-running diagnostic with more complete profile.",
                 "Regulatory uncertainty in fintech and healthtech sectors.",
                 "Talent acquisition cost rising due to diaspora competition."],
        generated_by="deterministic",
    )


# SEAM 6: BOARD SUMMARY

def _build_board_summary_prompt(
    readiness_report: ReadinessReport,
    bottlenecks: list[BottleneckAnalysis],
    decompositions: list[ScoreDecomposition],
    archetype: FounderArchetype,
    top_actions: list[CounterfactualResult],
) -> str:
    bottleneck_lines = "\n".join(
        f"  - {b.bottleneck_node_id} ({b.bottleneck_type}): blocks {b.blocked_potential:.1f} readiness pts"
        for b in bottlenecks[:3]
    ) or "  - (none material)"
    decomp_lines = "\n".join(
        f"  - {d.score_name}: {d.composite_value:.0f}/100, λ_cost={d.lambda_penalty_cost:.1f}, "
        f"top cause: {d.top_reduction_causes[0] if d.top_reduction_causes else 'n/a'}"
        for d in decompositions
    )
    action_lines = "\n".join(
        f"  - {a.action_title}: gain {a.overall_readiness_gain:+.2f} pts, leverage {a.leverage:.2f}, effort {a.effort:.1f} weeks"
        for a in top_actions[:5]
    ) or "  - (no high-leverage actions identified)"

    return f"""You write a one-page board/investor summary for a startup diagnostic platform.
Use ONLY the facts below. This is McKinsey/VC memo register: precise, declarative, no fluff, no hedging filler.

ARCHETYPE: {archetype.label} (confidence {archetype.confidence:.0%}, evidence quality {archetype.evidence_quality:.0%})
  {archetype.pattern_description}

READINESS:
  overall_readiness = {readiness_report.overall_readiness:.1f}/100
  readiness_without_dependency_penalty = {readiness_report.readiness_without_penalty:.1f}/100
  bottleneck_cost = {readiness_report.bottleneck_cost:.1f} pts
  weakest_link_floor = {readiness_report.weakest_link_floor:.1f}

DIMENSION DECOMPOSITION:
{decomp_lines}

STRUCTURAL BOTTLENECKS:
{bottleneck_lines}

TOP RECOMMENDED ACTIONS (already ranked by computed leverage):
{action_lines}

Produce exactly these four fields, each 1-3 sentences, citing real numbers above:
- executive_summary: overall state and trajectory
- key_risk: the single most material risk, tied to a specific bottleneck or score
- main_opportunity: the single highest-leverage opportunity, tied to a specific action/gain number
- strategic_focus: the one thing leadership should prioritize this quarter

Return ONLY valid JSON:
{{"executive_summary":"...","key_risk":"...","main_opportunity":"...","strategic_focus":"..."}}"""


def _board_summary_deterministic(
    readiness_report: ReadinessReport,
    bottlenecks: list[BottleneckAnalysis],
    top_actions: list[CounterfactualResult],
) -> BoardSummary:
    """
    Deterministic fallback for seam 6, used when the LLM is unavailable
    or disabled. Built only from already-computed decision-layer outputs
    — no fabricated content, just template sentences around real numbers.
    """
    top_bottleneck = bottlenecks[0] if bottlenecks else None
    top_action = top_actions[0] if top_actions else None
    return BoardSummary(
        executive_summary=(
            f"Overall readiness is {readiness_report.overall_readiness:.1f}/100. "
            f"Dependency penalties account for {readiness_report.bottleneck_cost:.1f} points of the gap "
            f"between raw and effective performance."
        ),
        key_risk=(
            f"{top_bottleneck.bottleneck_node_id} blocks {top_bottleneck.blocked_potential:.1f} readiness points."
            if top_bottleneck else
            "No single structural bottleneck dominates; risk is distributed across dimensions."
        ),
        main_opportunity=(
            f"'{top_action.action_title}' offers {top_action.overall_readiness_gain:+.2f} readiness points "
            f"at leverage {top_action.leverage:.2f} for {top_action.effort:.1f} founder-weeks."
            if top_action else
            "No high-leverage action currently dominates; incremental evidence confirmation is the safest next step."
        ),
        strategic_focus=(
            f"Address the weakest-link floor at {readiness_report.weakest_link_floor:.1f} before investing "
            "further in already-strong dimensions, per the weakest-link readiness model."
        ),
        generated_by="deterministic",
    )


async def _generate_board_summary(
    readiness_report: ReadinessReport,
    bottlenecks: list[BottleneckAnalysis],
    decompositions: list[ScoreDecomposition],
    archetype: FounderArchetype,
    top_actions: list[CounterfactualResult],
) -> BoardSummary:
    """
    Seam 6. Pure narrative synthesis across already-computed deterministic
    outputs. No number here is generated by the LLM — every figure quoted
    in the prompt comes from ReadinessReport / BottleneckAnalysis /
    ScoreDecomposition / CounterfactualResult, all decision-layer outputs.
    """
    prompt = _build_board_summary_prompt(readiness_report, bottlenecks, decompositions, archetype, top_actions)
    parsed = await _groq_chat_json_async(prompt, max_tokens=500, temperature=0.25)

    required = ("executive_summary", "key_risk", "main_opportunity", "strategic_focus")
    if parsed and all(isinstance(parsed.get(k), str) and parsed[k].strip() for k in required):
        return BoardSummary(
            executive_summary=parsed["executive_summary"].strip(),
            key_risk=parsed["key_risk"].strip(),
            main_opportunity=parsed["main_opportunity"].strip(),
            strategic_focus=parsed["strategic_focus"].strip(),
            generated_by="llm:qwen3-32b",
        )

    return _board_summary_deterministic(readiness_report, bottlenecks, top_actions)


# 12. MAIN SERVICE

class ScoringIntelligenceService:
    """
    Orchestrator for all intelligence layers.

    PHILOSOPHY:
      Deterministic engines (WeightedRuleScoreCalculator,
      GraphWeightedReadinessEngine, CounterfactualEngine,
      ContextualMutationEngine, DimensionGraphEngine, ContributionAnalyser,
      ArchetypeEngine.detect) make every decision and every number in this
      report. 
      The LLM (Qwen3-32B via Groq, free tier) is called in exactly
      five live seams — archetype narrative, recommendation sequencing,
      SWOT, milestone rationale, board summary — and every one of them
      receives finished numbers and returns text. A sixth seam (sector
      knowledge base) is offline/build-time only and never touches the
      network at request time.

    USAGE:
      svc = ScoringIntelligenceService(resource_service=res_svc)
      report = await svc.analyse(profile, scores)
      report = svc.analyse_sync(profile, scores)   # synchronous, no LLM wait

    GROQ:
      export GROQ_API_KEY=gsk_...
      If not set, every narrative seam falls back deterministically.
      No code change required, no crash, no fabricated numbers either way.

    DISABLING LLM SEAMS FOR TESTS / CI:
      ScoringIntelligenceService(use_llm=False) forces every seam to its
      deterministic fallback without needing to unset the environment
      variable — useful for fast, deterministic unit tests.
    """

    def __init__(
        self,
        resource_service: Any = None,
        lambda_penalty: float = LAMBDA_DEFAULT,
        sector_kb_dir: str | None = "data/knowledge_base/sector_actions",
        use_llm: bool = True,
    ) -> None:
        if not 0.0 <= lambda_penalty <= 1.0:
            raise ValueError(f"lambda_penalty must be in [0,1], got {lambda_penalty}")

        self._retriever = ResourceRetriever(resource_service)
        self._readiness = GraphWeightedReadinessEngine()
        self._mutation = ContextualMutationEngine()
        self._analyser = ContributionAnalyser()
        self._archetype = ArchetypeEngine()
        self._kb = SectorKnowledgeBase(sector_kb_dir) if sector_kb_dir else None
        self._use_llm = use_llm

        try:
            self._calculator = WeightedRuleScoreCalculator(lambda_penalty=lambda_penalty)
        except Exception:
            self._calculator = None

        self._cf = CounterfactualEngine(self._calculator, self._readiness)

    async def analyse(self, profile: Any, scores: Any) -> IntelligenceReport:
        # ── Decision layer: every number below is deterministic ──────────
        graph = DimensionGraphEngine(scores, profile)
        bottlenecks = graph.get_bottlenecks()
        archetype = self._archetype.detect(scores, profile)  # narrative seam fires inside .detect() -> _build()
        readiness_report = self._readiness.compute(scores)

        search = RecommendationSearchEngine(
            self._cf, self._mutation, graph, self._readiness,
            knowledge_base=self._kb, use_llm_narrative=self._use_llm,
        )
        top_actions, roadmap = search.run(profile, scores, archetype.archetype_id, bottlenecks)

        decompositions = [self._analyser.analyse(s, profile, s.name) for s in scores.scores]
        explanations = self._build_explanations(scores, decompositions, bottlenecks)
        resources = self._retriever.retrieve(profile, scores)
        conf_signals = _generate_confidence_signals(scores, profile)

        # _generate_board_summary() and _call_groq_swot_async() each
        # already perform the GROQ_API_KEY check internally (via
        # _groq_chat_json_async -> _groq_chat_json) and fall back to a
        # deterministic, input-grounded rendering on their own. The
        # `use_llm` flag here is a hard override for tests/CI: when False,
        # we skip the network attempt entirely rather than relying on the
        # env var, but we still go through the SAME fallback builders so
        # there is exactly one code path per seam, not two.
        if self._use_llm:
            swot_prompt = _build_swot_prompt(profile, scores, archetype, decompositions, readiness_report, bottlenecks)
            swot = await _call_groq_swot_async(swot_prompt)
            board_summary = await _generate_board_summary(
                readiness_report, bottlenecks, decompositions, archetype, top_actions,
            )
        else:
            swot = _swot_deterministic()
            board_summary = _board_summary_deterministic(
                readiness_report, bottlenecks, top_actions,
            )

        return IntelligenceReport(
            roadmap=roadmap, resources=resources, top_actions=top_actions,
            explanations=explanations, bottlenecks=bottlenecks, swot=swot,
            archetype=archetype, confidence_signals=conf_signals,
            readiness_report=readiness_report, board_summary=board_summary,
            overall_readiness=round(readiness_report.overall_readiness, 2),
        )

    def analyse_sync(self, profile: Any, scores: Any) -> IntelligenceReport:
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.analyse(profile, scores))
        finally:
            loop.close()

    def _build_explanations(self, scores, decompositions, bottlenecks):
        dmap = {d.score_name: d for d in decompositions}
        bn_dim = {b.bottleneck_node_id: b for b in bottlenecks if b.bottleneck_type == "dimension"}
        bn_crit: dict[str, BottleneckAnalysis] = {}
        for b in bottlenecks:
            if b.bottleneck_type == "fundamental_criterion":
                dim = b.bottleneck_node_id.split("::")[0]
                bn_crit.setdefault(dim, b)

        explanations: list[ScoreExplanation] = []
        for score in scores.scores:
            if score.value >= 75 and score.confidence >= 0.45 and not score.anomalies:
                continue
            decomp = dmap.get(score.name)
            bn = bn_dim.get(score.name) or bn_crit.get(score.name)
            conf_sig: str | None = None
            if score.value > 65 and score.confidence < 0.45 and decomp:
                best_u = max(
                    (c for c in decomp.criterion_contributions if c.evidence_status != "confirmed"),
                    key=lambda c: c.weight, default=None,
                )
                if best_u:
                    conf_sig = (
                        f"{score.name} is {score.value:.0f}/100 but confidence is {score.confidence:.0%}. "
                        f"Upload '{best_u.criterion_name}' (w={best_u.weight:.0%}) "
                        f"to recover {best_u.weight*100:.0f}% confidence."
                    )
            qw = []
            if decomp:
                qw += [c.split(".")[0] + "." for c in decomp.top_reduction_causes[:2]]
            if score.anomalies:
                qw.append(f"Resolve anomaly: {score.anomalies[0].replace('_', ' ')}.")
            if score.missing_criteria:
                qw.append(f"Complete intake for: {', '.join(score.missing_criteria[:2])}.")
            _empty_decomp = ScoreDecomposition(
                score_name=score.name, composite_value=score.value, c_base=score.value,
                lambda_penalty_cost=0.0, lambda_penalty_fraction=0.0,
                weakest_fundamental_criterion=None, weakest_fundamental_value=None,
                criterion_contributions=[], anomaly_penalties=[], anomaly_confidence_cost=0.0,
                top_reduction_causes=[], missing_evidence_cost=0.0, confidence_value=score.confidence,
            )
            explanations.append(ScoreExplanation(
                score_name=score.name, decomposition=decomp or _empty_decomp,
                bottleneck_explanation=bn.explanation if bn else None,
                high_score_low_confidence_signal=conf_sig,
                quick_wins=qw[:3],
            ))
        return explanations


# 13. REPORT SERIALISER

def report_to_dict(report: IntelligenceReport) -> dict[str, Any]:
    def _c(obj: Any) -> Any:
        if hasattr(obj, "__dataclass_fields__"): return {k: _c(v) for k, v in obj.__dict__.items()}
        if isinstance(obj, list): return [_c(i) for i in obj]
        if isinstance(obj, dict): return {k: _c(v) for k, v in obj.items()}
        if isinstance(obj, Enum): return obj.value
        if isinstance(obj, float): return round(obj, 4)
        return obj
    return _c(report)


# OFFLINE GENERATOR ENTRY POINT (seam 5 — sketch only, run separately,
# never imported by the runtime service above)

# Usage (run once, offline, commit the output):
#   GROQ_API_KEY=gsk_... python -m services.scripts.generate_sector_kb \
#       --sectors saas deeptech greentech fintech healthtech \
#       --out data/knowledge_base/sector_actions/

# This is intentionally NOT wired into ScoringIntelligenceService — it is
# a one-time (or periodically re-run, human-reviewed) build step. The
# generated JSON is then loaded at runtime by SectorKnowledgeBase
# (section 5 above) with zero network calls.

_OFFLINE_SECTOR_KB_PROMPT_TEMPLATE = """You design startup roadmap actions for the {sector} sector.
For each action, an action is later evaluated by a deterministic counterfactual
engine that applies your suggested mutation_hints to a real founder profile and
recomputes actual scores — your job is only to propose plausible, sector-grounded
actions and field deltas; you do not decide the final score impact.

Known ProjectProfile numeric/boolean fields you may reference in mutation_hints:
  market_size_known (bool), paying_customers (int), revenue_model_clarity (0-100),
  competition_understanding (0-100), process_automation_level (0-1),
  tech_stack_scalability (0-100), team_size (int), infrastructure_readiness (0-100),
  technology_readiness_level (1-9), problem_novelty_score (0-100), ip_assets (list),
  rd_investment_ratio (0-1), has_mvp (bool), process_documentation_score (0-100),
  financial_model_quality (0-100), legal_compliance_score (0-100),
  climate_air_impact_score (0-100), water_impact_score (0-100),
  soil_biodiversity_score (0-100), resources_waste_score (0-100),
  sdg_alignment_score (0-100), documented_interviews (int),
  market_validation_evidence (list).

Propose 4-6 actions specific to {sector}. Return ONLY a JSON list:
[
  {{
    "title": "...",
    "description": "...",
    "effort": <float founder-weeks, one of 0.5, 1.5, 3.0, 6.0, 12.0>,
    "mutation_hints": {{"field_name": new_value_or_delta, ...}},
    "addresses_criteria": ["..."],
    "resource_tags": ["..."],
    "dependencies": [],
    "assumptions": ["..."]
  }}
]"""
from enum import Enum


class CountryCode(str, Enum):
    TN = "TN"
    MA = "MA"
    DZ = "DZ"


class BusinessType(str, Enum):
    TRADITIONAL_BUSINESS = "traditional_business"
    STARTUP = "startup"


class ActorType(str, Enum):
    ENTREPRENEUR = "entrepreneur"
    STARTUPPER = "startupper"


class MaturityStage(str, Enum):
    IDEATION = "IDEATION"
    MARKET_VALIDATION = "MARKET_VALIDATION"
    STRUCTURATION = "STRUCTURATION"
    FUNDRAISING = "FUNDRAISING"
    LAUNCH_PLANNING = "LAUNCH_PLANNING"
    GROWTH = "GROWTH"


class GapLevel(str, Enum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class BlockerType(str, Enum):
    MARKET_VALIDATION = "MARKET_VALIDATION_BLOCKER"
    LEGAL = "LEGAL_BLOCKER"
    FINANCIAL = "FINANCIAL_BLOCKER"
    TEAM = "TEAM_BLOCKER"
    COMMERCIAL = "COMMERCIAL_BLOCKER"
    TECHNICAL = "TECHNICAL_BLOCKER"
    SCALABILITY = "SCALABILITY_BLOCKER"
    GREEN = "GREEN_BLOCKER"
    ADMINISTRATIVE = "ADMINISTRATIVE_BLOCKER"
    EXPORT = "EXPORT_BLOCKER"
    TENDER_READINESS = "TENDER_READINESS_BLOCKER"


class EligibilityStatus(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    POSSIBLY_ELIGIBLE = "POSSIBLY_ELIGIBLE"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class RoadmapHorizon(str, Enum):
    IMMEDIATE = "IMMEDIATE"
    SHORT_TERM = "SHORT_TERM"
    MEDIUM_TERM = "MEDIUM_TERM"


class ActionStatus(str, Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"


class QuestionType(str, Enum):
    TEXT = "text"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    SINGLE_CHOICE = "single_choice"
    MULTI_CHOICE = "multi_choice"


class TenderReadinessStatus(str, Enum):
    NOT_READY = "NOT_READY"
    READY_FOR_SMALL_TENDERS = "READY_FOR_SMALL_TENDERS"
    READY_WITH_PARTNER = "READY_WITH_PARTNER"
    READY = "READY"


class EvidenceStatus(str, Enum):
    """Shared contract for the per-field state of the evidence ledger."""

    CONFIRMED = "CONFIRMED"
    UNVERIFIED = "UNVERIFIED"
    CONTRADICTED = "CONTRADICTED"
    MISSING = "MISSING"


class EvidenceStage(str, Enum):
    """Document-evidence-gated maturity taxonomy (S1-S6).

    Stages gate on real artifacts (RNE, TVA, CNSS, factures), not declared
    intent. The intake engine encodes which evidence field each gate needs; it
    never assigns the stage. See docs/intake-engine.md for the crosswalk to
    ``MaturityStage``.
    """

    S1 = "S1"  # idea-only
    S2 = "S2"  # problem validated / informal
    S3 = "S3"  # prototype + entity started
    S4 = "S4"  # real commercial traction (factures w/ TVA, SARL/SUARL)
    S5 = "S5"  # proven model + fiscal compliance
    S6 = "S6"  # investment-ready / scaling


class IntakePhase(str, Enum):
    """Four-phase progressive disclosure ordering for question selection."""

    FOUNDATION = "FOUNDATION"
    MARKET_CLIENTS = "MARKET_CLIENTS"
    MODEL_LEGAL = "MODEL_LEGAL"
    FINANCE_TEAM = "FINANCE_TEAM"


class ProbeKind(str, Enum):
    EVIDENCE = "EVIDENCE"
    SECTOR = "SECTOR"
    STAGE_SKIP = "STAGE_SKIP"


class MissingKind(str, Enum):
    """Classification of a frontier-relative information gap."""

    ASKABLE = "ASKABLE"  # field MISSING, ask a question
    NEEDS_PROBE = "NEEDS_PROBE"  # field UNVERIFIED, push an evidence probe
    STRUCTURAL_GAP = "STRUCTURAL_GAP"  # present but negative -> blocker, do not ask

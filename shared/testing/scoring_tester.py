from shared.contracts.schemas import ProjectProfile
from shared.domain.scoring import WeightedRuleScoreCalculator
from shared.contracts.schemas import EvidenceEntry
from shared.contracts.enums import EvidenceStatus


profile = ProjectProfile(

    sector="saas",

    declared_stage="MARKET_VALIDATION",

    has_mvp=True,

    paying_customers=5,

    documented_interviews=20,

    market_size_known=True,

    competition_understanding=70,

    revenue_model_clarity=60,


    team_size=3,

    process_documentation_score=70,

    financial_model_quality=50,

    legal_compliance_score=80,


    process_automation_level=0.7,

    tech_stack_scalability=80,

    infrastructure_readiness=75,


    technology_readiness_level=6,

    innovation_level=85,

    problem_novelty_score=85,

    rd_investment_ratio=0.2,


    climate_air_impact_score=50,
    water_impact_score=50,
    soil_biodiversity_score=50,
    resources_waste_score=50,
    sdg_alignment_score=60
)
profile.evidence_ledger={
    "paying_customers":
    EvidenceEntry(
        status=EvidenceStatus.CONFIRMED,
        source="customer_contracts"
    ),


    "technology_readiness_level":
    EvidenceEntry(
        status=EvidenceStatus.CONFIRMED,
        source="technical_report"
    ),


    "legal_compliance_score":
    EvidenceEntry(
        status=EvidenceStatus.CONFIRMED,
        source="legal_document"
    ),


    "team_size":
    EvidenceEntry(
        status=EvidenceStatus.CONFIRMED,
        source="company_record"
    ),
    "market_size_known":
        EvidenceEntry(
            status=EvidenceStatus.CONFIRMED
        )
}


calculator = WeightedRuleScoreCalculator()


result = calculator.compute(profile)


print("\n===== SCORES =====")

for score in result.scores:

    print(
        score.name,
        ":",
        score.value,
        "confidence:",
        score.confidence
    )

    print(
        "missing:",
        score.missing_criteria
    )

    print(
        "anomalies:",
        score.anomalies
    )
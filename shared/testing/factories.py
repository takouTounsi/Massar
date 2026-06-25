from shared.contracts.enums import BusinessType, CountryCode, MaturityStage
from shared.contracts.schemas import ProjectProfile


def case_market_validation_gap() -> ProjectProfile:
    return ProjectProfile(
        country=CountryCode.TN,
        business_type=BusinessType.STARTUP,
        declared_stage=MaturityStage.FUNDRAISING,
        primary_goal="funding",
        sector="technology",
        sub_sector="saas",
        has_mvp=True,
        has_revenue=False,
        paying_customers=0,
        documented_interviews=3,
        market_validation_evidence=[],
        market_size_known=False,
    )


def case_scalability_gap() -> ProjectProfile:
    return ProjectProfile(
        country=CountryCode.MA,
        business_type=BusinessType.STARTUP,
        declared_stage=MaturityStage.GROWTH,
        primary_goal="growth",
        sector="technology",
        sub_sector="saas",
        has_mvp=True,
        has_revenue=True,
        monthly_revenue=2500,
        recurring_revenue=True,
        paying_customers=12,
        documented_interviews=25,
        market_validation_evidence=["invoices", "retention cohort"],
        process_automation_level=0.2,
        team_size=3,
    )


def case_tender_not_ready() -> ProjectProfile:
    return ProjectProfile(
        country=CountryCode.DZ,
        business_type=BusinessType.TRADITIONAL_BUSINESS,
        declared_stage=MaturityStage.STRUCTURATION,
        primary_goal="public_procurement",
        sector="construction",
        has_mvp=True,
        has_revenue=False,
        paying_customers=1,
        documented_interviews=4,
        wants_public_tenders=True,
        administrative_documents_ready=False,
        financial_capacity_score=25,
        tender_references_count=0,
    )

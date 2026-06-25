from shared.contracts.schemas import Score, CompositeScores
from shared.domain.scoring_intelligence import GraphWeightedReadinessEngine


scores = CompositeScores(
    scores=[

        Score(
            name="Innovation Score",
            value=90,
            confidence=1,
            sub_scores=[],
            highest_leverage_action="Protect innovation assets",
            version="test-v1"
        ),

        Score(
            name="Market Score",
            value=20,
            confidence=1,
            sub_scores=[],
            highest_leverage_action="Validate customers",
            version="test-v1"
        ),

        Score(
            name="Operational Score",
            value=60,
            confidence=1,
            sub_scores=[],
            highest_leverage_action="Improve processes",
            version="test-v1"
        ),

        Score(
            name="Scalability Score",
            value=80,
            confidence=1,
            sub_scores=[],
            highest_leverage_action="Improve infrastructure",
            version="test-v1"
        ),

        Score(
            name="Green Score",
            value=70,
            confidence=1,
            sub_scores=[],
            highest_leverage_action="Improve sustainability",
            version="test-v1"
        )
    ]
)


engine = GraphWeightedReadinessEngine()

result = engine.compute(scores)

print(result)
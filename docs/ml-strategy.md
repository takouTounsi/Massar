# ML Strategy

The first version uses explainable rules before ML. Every decision service has a protocol-based interface:

- `MaturityPredictor`
- `ScoreCalculator`
- `BlockerDetector`
- `VersionedModel`

`SklearnMaturityPredictor` and `ModelBasedScoreCalculator` are implemented as safe fallback wrappers that currently delegate to rules. This keeps the API stable for future trained models without allowing an unvalidated model to drive decisions in the MVP.

Scores are never computed by an LLM.

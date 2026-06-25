# Domain Model

The core aggregate is `ProjectProfile`, versioned by `project_id`. The profile separates country, actor type, business type, declared stage, goal, legal state, traction, market evidence, tender readiness and scoring inputs.

The mandatory maturity taxonomy is:

- `IDEATION`
- `MARKET_VALIDATION`
- `STRUCTURATION`
- `FUNDRAISING`
- `LAUNCH_PLANNING`
- `GROWTH`

Decision outputs are structured as `MaturityPrediction`, `CompositeScores`, `BlockerResult`, `ConfidenceReport`, `ResourceMatch`, `EligibilityResult` and `Roadmap`.

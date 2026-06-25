# Evaluation Plan

The synthetic evaluation plan tracks:

- `maturity_accuracy`
- `maturity_macro_f1`
- `blocker_micro_f1`
- `blocker_macro_f1`
- `score_consistency`
- `retrieval_precision_at_3`
- `eligibility_accuracy`
- `roadmap_grounding_rate`
- `average_latency`

`scripts/evaluate_maturity_model.py` writes a deterministic MVP report to `data/evaluation/maturity_report.json`.

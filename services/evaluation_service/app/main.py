from shared.application.fastapi import create_service_app

app = create_service_app("Evaluation Service", "evaluation_service")


@app.post("/evaluation/run")
async def run_evaluation() -> dict[str, float]:
    return {
        "maturity_accuracy": 0.75,
        "maturity_macro_f1": 0.72,
        "blocker_micro_f1": 0.78,
        "blocker_macro_f1": 0.74,
        "score_consistency": 0.83,
        "retrieval_precision_at_3": 0.8,
        "eligibility_accuracy": 0.77,
        "roadmap_grounding_rate": 1.0,
        "average_latency": 0.0,
    }

from __future__ import annotations

import os
import re
from typing import Optional, Any
from dotenv import load_dotenv
try:
    from google import genai
except ImportError:  # SDK is optional; callers fall back to local heuristics.
    genai = None


load_dotenv()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if GEMINI_API_KEY and genai is not None:
    client = genai.Client(api_key=GEMINI_API_KEY)
else:
    client = None


def gemini_classify(
    free_text: str,
    options: list[str],
    context: dict,
    model: str = "gemini-2.5-flash",
) -> int:
    """Classify `free_text` into one of `options` using Gemini.

    Falls back to returning 0 when the API is not configured or
    the response cannot be parsed into a valid index.
    """
    if client is None:
        # Signal to callers that the provider is not configured so higher
        # level code (LLMClassifier) can fall back to a local heuristic.
        raise RuntimeError("GEMINI_API_KEY not configured; cannot call Gemini API")

    options_block = "\n".join(f"{i}: {option}" for i, option in enumerate(options))

    prompt = f"""
A startup founder was asked:

{context.get("question", "")}

They answered:

"{free_text}"

Map the answer to the SINGLE closest option below.

Rules:
- Return ONLY the option number.
- No explanation.
- No extra text.

Options:
{options_block}
"""

    response = client.models.generate_content(
        model=model,
        contents=prompt,
    )

    # Some SDKs put the text on .text, others in nested structures.
    text = getattr(response, "text", None)
    if text is None:
        try:
            text = str(response)
        except Exception:
            text = ""

    text = text.strip()
    match = re.search(r"\d+", text)
    if not match:
        return 0

    idx = int(match.group())
    if idx < 0 or idx >= len(options):
        return 0
    return idx


def gemini_generate_followups(
    company_description: str,
    candidate_nodes: list[dict],
    max_questions: int = 3,
    model: str = "gemini-2.5-flash",
) -> list[dict]:
    """Generate targeted follow-up questions mapped to candidate tree node IDs.

    `candidate_nodes` is a list of dicts with keys: `node_id`, `phase`, `dimension`, `question`.
    Returns a list of dicts: {"question": str, "target_node_id": str}.
    """
    if client is None:
        raise RuntimeError("GEMINI_API_KEY not configured; cannot call Gemini API")

    candidates_block = "\n".join(
        f"{i}: id={c['node_id']} phase={c.get('phase','')} dim={c.get('dimension','')} text={c.get('question','')}"
        for i, c in enumerate(candidate_nodes)
    )

    prompt = f"""
You are given a brief description of a startup and a list of candidate diagnostic nodes used by a structured decision tree.

Startup description:
{company_description}

Candidate nodes (format: index: id=... phase=... dim=... text=...):
{candidates_block}

Task:
- Propose up to {max_questions} follow-up questions (concise) that would best help determine which of the candidate nodes is applicable.
- For each question, return a JSON object with keys: "question" (string) and "target_node_id" (the node_id exactly as listed above).
- Return a JSON array only, no surrounding text.

Example output:
[
  {{"question": "...", "target_node_id": "123"}},
]
"""

    response = client.models.generate_content(model=model, contents=prompt)
    text = getattr(response, "text", None)
    if text is None:
        try:
            text = str(response)
        except Exception:
            text = ""

    text = text.strip()

    # Try to extract JSON array from output
    import json
    match = None
    try:
        # direct parse
        arr = json.loads(text)
    except Exception:
        # fallback: find first '[' and last ']' and parse
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            try:
                arr = json.loads(text[start:end+1])
            except Exception:
                arr = []
        else:
            arr = []

    results = []
    for item in (arr or [])[:max_questions]:
        if isinstance(item, dict) and "question" in item and "target_node_id" in item:
            results.append({"question": item["question"], "target_node_id": item["target_node_id"]})

    return results

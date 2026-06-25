import json
from dataclasses import dataclass
from typing import Optional, List, Dict

from shared.application.startup_classifier import (
    DecisionNode,
    build_industry_tree,
    INDUSTRIES_BY_KEY,
    LLMClassifier,
)
from shared.application.startup_classifier import generate_followups_for_tree


# Special initial open-ended node id
START_COMPANY_NODE_ID = "company_description"


class RouterError(Exception):
    """
    Custom exception for router-level errors.
    Web frameworks can catch this and map `.message` to an HTTP 400 response.
    """
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ==========================================
# DATA CONTRACTS
# ==========================================

@dataclass
class OptionPayload:
    index: int
    text: str


@dataclass
class TranscriptEntry:
    node_id: str
    question: str
    chosen_answer_text: str


@dataclass
class QuestionPayload:
    session_industry_key: str
    node_id: str
    phase: Optional[str]
    dimension: Optional[str]
    question: str
    explanation: Optional[str]
    allow_free_text: bool
    options: List[OptionPayload]
    is_terminal: bool = False


@dataclass
class ResultPayload:
    session_industry_key: str
    node_id: str
    phase: str
    result_text: str
    transcript: List[TranscriptEntry]
    is_terminal: bool = True


@dataclass
class AnswerRequest:
    session_industry_key: str
    node_id: str
    selected_option_index: Optional[int]
    free_text: Optional[str]
    transcript_so_far: List[TranscriptEntry]


# ==========================================
# STATELESS ROUTER & CORE FUNCTIONS
# ==========================================

_TREE_INDEX_CACHE: Dict[str, Dict[str, DecisionNode]] = {}


def get_node_by_id(root_node: DecisionNode, node_id: str) -> Optional[DecisionNode]:
    tree_cache_key = root_node.node_id

    if tree_cache_key not in _TREE_INDEX_CACHE:
        index: Dict[str, DecisionNode] = {}
        visited = set()
        queue = [root_node]

        while queue:
            curr = queue.pop(0)
            if curr.node_id not in visited:
                visited.add(curr.node_id)
                index[curr.node_id] = curr

                if getattr(curr, 'phase_result', None) is None:
                    for _, next_node in getattr(curr, 'options', []):
                        if next_node.node_id not in visited:
                            queue.append(next_node)

        _TREE_INDEX_CACHE[tree_cache_key] = index

    return _TREE_INDEX_CACHE[tree_cache_key].get(node_id)


def to_question_payload(node: DecisionNode, industry_key: str, override_question: str | None = None) -> QuestionPayload:
    options = [
        OptionPayload(index=i, text=opt_text)
        for i, (opt_text, _) in enumerate(getattr(node, 'options', []))
    ]

    return QuestionPayload(
        session_industry_key=industry_key,
        node_id=node.node_id,
        phase=getattr(node, 'phase', None),
        dimension=getattr(node, 'dimension', None),
        question=override_question or node.question,
        explanation=getattr(node, 'explanation', None),
        allow_free_text=getattr(node, 'allow_free_text', False),
        options=options,
        is_terminal=False
    )


def to_result_payload(node: DecisionNode, industry_key: str, transcript: List[TranscriptEntry]) -> ResultPayload:
    return ResultPayload(
        session_industry_key=industry_key,
        node_id=node.node_id,
        phase=getattr(node, 'phase', "UNKNOWN_PHASE"),
        result_text=node.phase_result,
        transcript=transcript,
        is_terminal=True
    )


def start_session(industry_key: str) -> QuestionPayload:
    if industry_key not in INDUSTRIES_BY_KEY:
        raise RouterError("INVALID_INDUSTRY", f"Unknown industry key: {industry_key}")

    # First, ask an open-ended company description. Generated follow-ups
    # will be produced by the LLM and mapped to existing tree nodes.
    return QuestionPayload(
        session_industry_key=industry_key,
        node_id=START_COMPANY_NODE_ID,
        phase=None,
        dimension=None,
        question="Please describe your company and what it does in detail.",
        explanation="Provide a short, precise description of product, customers, traction, and business model.",
        allow_free_text=True,
        options=[],
        is_terminal=False,
    )


def submit_answer(request: AnswerRequest, classifier: Optional[LLMClassifier] = None):
    if request.session_industry_key not in INDUSTRIES_BY_KEY:
        raise RouterError("INVALID_INDUSTRY", f"Unknown industry key: {request.session_industry_key}")

    root_node = build_industry_tree(INDUSTRIES_BY_KEY[request.session_industry_key])

    # Handle the special company description node: generate LLM follow-ups
    if request.node_id == START_COMPANY_NODE_ID:
        # must provide free text
        if not request.free_text or request.free_text.strip() == "":
            raise RouterError("INVALID_ANSWER", "Company description required.")
        # generate follow-ups targeting nodes in the tree
        followups = generate_followups_for_tree(request.free_text, root_node, max_q=3)
        if not followups:
            # fallback: return first root question
            return to_question_payload(root_node, request.session_industry_key)

        # choose first generated followup and map to existing node
        pick = followups[0]
        target_id = pick.get("target_node_id")
        target_node = get_node_by_id(root_node, target_id)
        if not target_node:
            # if mapping failed, fall back to root
            return to_question_payload(root_node, request.session_industry_key)

        # return the target node payload but override the question text
        return to_question_payload(target_node, request.session_industry_key, override_question=pick.get("question"))

    node = get_node_by_id(root_node, request.node_id)

    if not node:
        raise RouterError("INVALID_NODE_ID", f"Node '{request.node_id}' not found.")
    if getattr(node, 'phase_result', None) is not None:
        raise RouterError("ALREADY_TERMINAL", "Cannot submit an answer to a terminal leaf node.")

    has_option = request.selected_option_index is not None
    has_text = request.free_text is not None and request.free_text.strip() != ""

    if has_option and has_text:
        raise RouterError("AMBIGUOUS_ANSWER", "Provide either a selected option or free text, not both.")
    if not has_option and not has_text:
        raise RouterError("INVALID_ANSWER", "You must provide either a selected option or free text.")

    chosen_index = None

    if has_option:
        chosen_index = request.selected_option_index
        if chosen_index < 0 or chosen_index >= len(node.options):
            raise RouterError("INVALID_ANSWER", f"Option index {chosen_index} is out of bounds.")
    elif has_text:
        if not getattr(node, 'allow_free_text', False):
            raise RouterError("FREE_TEXT_NOT_ALLOWED", "This question does not accept free-text answers.")
        if not classifier:
            raise RouterError("CLASSIFIER_MISSING", "Free-text provided but no LLMClassifier is configured on the backend.")

        option_texts = [opt_text for opt_text, _ in node.options]
        try:
            # Pass a context dict (question + node_id) so LLM providers
            # that expect a mapping (use .get()) don't raise AttributeError.
            chosen_index = classifier.classify(
                request.free_text,
                option_texts,
                context={"question": node.question, "node_id": node.node_id},
            )
        except Exception as e:
            raise RouterError("CLASSIFICATION_FAILED", f"LLM Classification failed: {str(e)}")

        if chosen_index < 0 or chosen_index >= len(node.options):
            raise RouterError("CLASSIFICATION_FAILED", "Classifier returned an out-of-bounds index.")

    chosen_option_text, next_node = node.options[chosen_index]

    new_transcript = []
    for entry in request.transcript_so_far:
        if isinstance(entry, dict):
            new_transcript.append(TranscriptEntry(**entry))
        else:
            new_transcript.append(entry)

    new_transcript.append(TranscriptEntry(
        node_id=node.node_id,
        question=node.question,
        chosen_answer_text=chosen_option_text
    ))

    if getattr(next_node, 'phase_result', None) is not None:
        return to_result_payload(next_node, request.session_industry_key, new_transcript)
    else:
        return to_question_payload(next_node, request.session_industry_key)


# Framework-agnostic example wiring is omitted; this module exposes pure
# functions that can be plugged into FastAPI or another framework.

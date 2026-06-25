"""
================================================================================
 STARTUP PHASE CLASSIFIER — Deep Multi-Industry Edition
================================================================================

A decision-tree engine that determines which phase a startup is in:
    IDEATION -> MARKET_VALIDATION -> STRUCTURATION -> FUNDRAISING -> LAUNCH_PLANNING -> GROWTH

What's new in this version vs. the original prototype:

1. SHARED DEEP SKELETON
   A single core tree ("the spine") walks every founder through five phases.
   At each phase, the spine asks about FOUR dimensions, not just product status:
     - Product / technical maturity
     - Legal & compliance status (entity, IP, contracts, regulation)
     - Financial status (revenue, burn, funding, accounting)
     - Team & organization (size, hiring, structure)
   This is shared logic so we don't reimplement "have you incorporated yet"
   17 times.

2. INDUSTRY MODULES (17 of them)
   Each industry plugs fine-tuned question variants into the spine at each
   phase/dimension. A Fintech founder gets asked about regulatory licensing;
   a Mobility founder gets asked about vehicle homologation; an EdTech
   founder gets asked about data privacy for minors; etc. This is done via
   an IndustryProfile object that supplies industry-specific text for slots
   in the spine, rather than duplicating the whole tree per industry.

3. FREE-TEXT NODES + PLUGGABLE LLM CLASSIFIER
   Some questions accept free-form written explanations instead of forcing
   a multiple choice. A pluggable `llm_classify_fn` (you provide the actual
   API call) maps that free text onto the closest predefined option, with a
   transparent fallback heuristic when no LLM function is wired in.

4. JSON EXPORT CONTRACT
   The full tree (spine + all 17 industries) can be exported as JSON for a
   frontend to render, same contract style as the original code.

5. TEST / PERSONA HARNESS
   A set of canned "personas" (synthetic founders at various phases, in
   various industries, some answering in free text) is provided to
   automatically run the tree end-to-end without a human typing answers.
   This is for regression-testing the tree logic, not for talking to a
   real LLM in CI (it stubs the LLM call when none is provided).

Architecture notes:
- DecisionNode: a fixed multiple-choice question node (same idea as before).
- FreeTextNode: a question node that accepts free text, classifies it via
  the pluggable LLM hook against the same option set as a DecisionNode,
  then routes exactly like a DecisionNode would.
- IndustryProfile: a small data object holding the industry's display name
  and a dict of text overrides keyed by "slot id" used throughout the spine.
- build_industry_tree(profile): builds one full phase-spine tree wired with
  that industry's text.
- INDUSTRIES: the ordered list of the 17 industries from the user's spec,
  each mapped to a "family" (mobility/hardware-like, software-like,
  health & social, ecommerce-like) that determines which question pack
  the spine pulls phrasing from by default, with the IndustryProfile able
  to override any individual line.
"""

import json
import sys
from dataclasses import dataclass, field
from typing import Callable, Optional
from shared.llm.gemini_provider import gemini_classify
from shared.llm.gemini_provider import gemini_generate_followups


# ======================================================================
# SECTION 0: PLUGGABLE LLM CLASSIFICATION HOOK
# ======================================================================
LLMClassifyFn = Callable[[str, list, dict], int]


_STOPWORDS_FR = {
    "le", "la", "les", "un", "une", "des", "de", "du", "et", "ou", "est",
    "sont", "il", "elle", "nous", "vous", "ils", "elles", "on", "ne", "pas",
    "que", "qui", "ce", "ça", "se", "pour", "avec", "sur", "dans", "plus",
    "encore", "déjà", "mais", "donc", "j", "l", "d", "à", "au", "aux", "en",
    "avoir", "avez", "avons", "ai", "a", "j'ai",
}


def fallback_keyword_classifier(free_text: str, options: list, context: dict) -> int:
    def clean_words(text):
        words = text.lower().replace(",", "").replace(".", "").replace("?", "").split()
        return [w for w in words if w not in _STOPWORDS_FR and len(w) > 2]

    text_words = clean_words(free_text)
    best_idx = 0
    best_score = -1.0
    for i, opt in enumerate(options):
        opt_words = set(clean_words(opt))
        score = sum(len(w) for w in text_words if w in opt_words)
        if score > best_score:
            best_score = score
            best_idx = i
    return best_idx


def generate_followups_for_tree(free_text: str, root_node, max_q: int = 3):
    """Generate follow-up questions mapped to nodes in the provided tree.

    Falls back to a simple heuristic when LLM is not available.
    Returns list of dicts {"question": str, "target_node_id": str}.
    """
    # collect candidate nodes: non-terminal, prefer nodes with phase/dimension metadata
    candidates = []
    visited = set()
    queue = [root_node]
    while queue and len(candidates) < 100:
        curr = queue.pop(0)
        if curr.node_id in visited:
            continue
        visited.add(curr.node_id)
        if getattr(curr, 'phase_result', None) is None:
            candidates.append({
                "node_id": curr.node_id,
                "phase": getattr(curr, 'phase', ''),
                "dimension": getattr(curr, 'dimension', ''),
                "question": curr.question or "",
            })
            for _, next_node in getattr(curr, 'options', []):
                if next_node.node_id not in visited:
                    queue.append(next_node)

    # Try LLM path
    try:
        picks = gemini_generate_followups(free_text, candidates, max_questions=max_q)
        if picks:
            return picks
    except Exception:
        pass

    # Heuristic fallback: select nodes whose question words overlap with company text
    def words(text):
        return set([w.lower().strip(".,?')(") for w in text.split() if len(w) > 3])

    fw = words(free_text)
    scored = []
    for c in candidates:
        score = len(fw & words(c.get('question','')))
        scored.append((score, c))
    scored.sort(key=lambda x: -x[0])
    out = []
    for score, c in scored[:max_q]:
        qtext = f"Can you elaborate on: {c.get('question')}"
        out.append({"question": qtext, "target_node_id": c['node_id']})
    return out


@dataclass
class LLMClassifier:
    """Wrapper so we can pass one object around instead of a bare function."""
    classify_fn: Optional[LLMClassifyFn] = None
    label: str = "unconfigured-fallback"

    def classify(self, free_text: str, options: list, context: dict) -> int:
        if self.classify_fn is not None:
            try:
                idx = self.classify_fn(free_text, options, context)
                if isinstance(idx, int) and 0 <= idx < len(options):
                    return idx
            except Exception as exc:  # noqa: BLE001 - we want a safe fallback
                print(f"⚠️  LLM classify_fn raised {exc!r}; falling back to heuristic.")
        return fallback_keyword_classifier(free_text, options, context)


def demo_test_classify_fn(free_text: str, options: list, context: dict) -> int:
    lowered = free_text.lower()
    if "juste la fonctionnalité de base" in lowered or "fonctionnalité de base" in lowered:
        # matches "ça fonctionne mais seulement sur la fonctionnalité principale"
        for i, opt in enumerate(options):
            if "seulement" in opt.lower() or "fonctionnalité principale" in opt.lower():
                return i
    return fallback_keyword_classifier(free_text, options, context)


DEMO_TEST_CLASSIFIER = LLMClassifier(classify_fn=demo_test_classify_fn, label="demo-test-classifier")

# General-purpose default used by the interactive app and evaluate_with_answers
# when no classifier is supplied. Uses the keyword-overlap fallback until you
# wire a real `llm_classify_fn` in (see module docstring for an example).
DEFAULT_CLASSIFIER = LLMClassifier(gemini_classify)


# ======================================================================
# SECTION 1: CORE NODE TYPES
# ======================================================================

class DecisionNode:
    """A node in the decision tree that supports multiple-choice questions,
    free-text explanation, and rich paths. Each node belongs to a `phase`
    and a `dimension` (product / legal / financial / team) purely as
    metadata used for reporting and JSON export — it doesn't change
    traversal logic."""

    def __init__(self, node_id, question=None, explanation=None,
                 phase_result=None, phase=None, dimension=None,
                 allow_free_text=False):
        self.node_id = node_id
        self.question = question
        self.explanation = explanation
        self.options = []  # list of (option_text, next_node)
        self.phase_result = phase_result
        self.phase = phase
        self.dimension = dimension
        # If True, an interactive run offers a "explain in your own words"
        # path that gets routed through the LLM classifier onto one of the
        # fixed options below.
        self.allow_free_text = allow_free_text

    def add_option(self, option_text, next_node):
        self.options.append((option_text, next_node))
        return self  # allow chaining

    # ---- JSON CONTRACT -------------------------------------------------
    def to_dict(self):
        if self.phase_result is not None:
            return {
                "type": "result",
                "phase": self.phase,
                "result_text": self.phase_result,
            }
        return {
            "type": "question",
            "phase": self.phase,
            "dimension": self.dimension,
            "question": self.question,
            "explanation": self.explanation,
            "allow_free_text": self.allow_free_text,
            "options": [
                {"text": opt_text, "next_node_id": next_node.node_id}
                for opt_text, next_node in self.options
            ],
        }

    # ---- INTERACTIVE TERMINAL EVALUATION --------------------------------
    def evaluate(self, classifier: "LLMClassifier" = None, transcript: list = None):
        """Interactive evaluation logic for terminal use.

        classifier: an LLMClassifier used to route free-text answers.
        transcript: optional list that records (question, answer, node_id)
                    tuples as the user moves through the tree — useful for
                    audits/logging and for the persona test harness.
        """
        classifier = classifier or DEFAULT_CLASSIFIER
        if transcript is None:
            transcript = []

        if self.phase_result is not None:
            return self.phase_result, transcript

        while True:
            print("\n" + "=" * 80)
            tag = f"[{self.phase}/{self.dimension}] " if self.phase else ""
            print(f"📌 {tag}QUESTION : {self.question}")
            if self.explanation:
                print(f"💡 EXPLICATION : {self.explanation}")
            print("-" * 80)

            for i, (opt_text, _) in enumerate(self.options, 1):
                print(f"  [{i}] {opt_text}")

            free_text_choice_num = len(self.options) + 1
            if self.allow_free_text:
                print(f"  [{free_text_choice_num}] ✍️  Expliquer avec mes propres mots")

            choice = input(f"\n👉 Votre choix : ").strip()

            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(self.options):
                    chosen_text = self.options[idx][0]
                    transcript.append((self.question, chosen_text, self.node_id))
                    return self.options[idx][1].evaluate(classifier, transcript)
                if self.allow_free_text and idx == len(self.options):
                    free_text = input("✍️  Expliquez votre situation : ").strip()
                    option_texts = [opt for opt, _ in self.options]
                    best_idx = classifier.classify(
                        free_text, option_texts,
                        context={"question": self.question, "node_id": self.node_id},
                    )
                    print(f"🤖 Réponse classée comme : « {option_texts[best_idx]} »")
                    transcript.append((self.question, f"[free-text] {free_text}", self.node_id))
                    return self.options[best_idx][1].evaluate(classifier, transcript)

            print(f"\n❌ Choix invalide. Veuillez entrer un numéro valide.")

    # ---- NON-INTERACTIVE EVALUATION (for the persona test harness) -----
    def evaluate_with_answers(self, answers: dict, classifier: "LLMClassifier" = None,
                               transcript: list = None):
        """Walks the tree using a pre-supplied `answers` dict instead of
        stdin, so personas can be run automatically in tests.

        `answers` maps node_id -> either:
          - an int (index of the chosen option, 0-based), or
          - a string starting with "FREE:" followed by free text, which
            gets routed through the classifier exactly like the
            interactive free-text path.

        If a node_id is missing from `answers`, we default to picking
        option 0, so partial persona definitions still run to completion.
        """
        classifier = classifier or DEFAULT_CLASSIFIER
        if transcript is None:
            transcript = []

        if self.phase_result is not None:
            return self.phase_result, transcript

        ans = answers.get(self.node_id, 0)

        if isinstance(ans, str) and ans.startswith("FREE:"):
            free_text = ans[len("FREE:"):].strip()
            option_texts = [opt for opt, _ in self.options]
            idx = classifier.classify(
                free_text, option_texts,
                context={"question": self.question, "node_id": self.node_id},
            )
            transcript.append((self.node_id, f"[free-text] {free_text}", option_texts[idx]))
        else:
            idx = int(ans)
            idx = max(0, min(idx, len(self.options) - 1))
            transcript.append((self.node_id, idx, self.options[idx][0]))

        next_node = self.options[idx][1]
        return next_node.evaluate_with_answers(answers, classifier, transcript)


# ==============================================================================
# SECTION 2: INDUSTRY PROFILES
# ==============================================================================
# Each IndustryProfile supplies fine-tuned phrasing for ~30 "slots" used by
# the shared spine (built in Section 3). A slot is a short string key like
# "legal_q_ip" or "product_q_poc". If an industry doesn't override a slot,
# the spine falls back to a generic line for that slot's "family"
# (mobility/hardware, software/digital, health & social, ecommerce/retail).
#
# This is what gives "much much more depth" without hand-writing 17
# completely separate trees: the spine logic, ordering, and dimension
# coverage (product/legal/financial/team) is identical across industries,
# but every single question's wording is industry-specific where it matters
# most (regulation, unit economics, compliance, typical milestones).

@dataclass
class IndustryProfile:
    key: str                      # menu key, e.g. "4"
    name: str                     # display name, e.g. "Fintech"
    family: str                   # "hardware" | "software" | "health_social" | "ecommerce"
    overrides: dict = field(default_factory=dict)  # slot_id -> text

    def text(self, slot_id: str, fallback: str) -> str:
        return self.overrides.get(slot_id, fallback)

    
# ---- 17 INDUSTRIES, AS SPECIFIED ------------------------------------------
INDUSTRIES: list = [
    IndustryProfile(
        key="1", name="Mobility", family="hardware",
        overrides={
            "legal_q_regulatory": "Avez-vous obtenu les homologations nécessaires (type d'approbation véhicule, autorisation de circulation, licence de transport) ?",
            "legal_explanation_regulatory": "Les véhicules et solutions de mobilité sont souvent soumis à des homologations nationales/régionales avant toute commercialisation ou mise en circulation.",
            "product_q_poc": "Avez-vous un prototype de véhicule, dispositif ou solution de mobilité qui fonctionne en conditions contrôlées (piste d'essai, simulation) ?",
            "product_q_pmf": "Des opérateurs de flotte, collectivités ou utilisateurs finaux ont-ils testé votre solution en conditions réelles de circulation ?",
            "financial_q_scale": "Votre coût unitaire de fabrication/déploiement par véhicule ou unité baisse-t-il avec le volume (économies d'échelle industrielles) ?",
            "team_q_growth": "Avez-vous des équipes dédiées à la sécurité routière, à la certification et aux opérations terrain dans plusieurs pays ?",
        },
    ),
    IndustryProfile(
        key="2", name="Health & Tech", family="health_social",
        overrides={
            "legal_q_regulatory": "Avez-vous identifié si votre produit est un dispositif médical et engagé les démarches de certification (marquage CE médical, FDA, ou équivalent local) ?",
            "legal_explanation_regulatory": "Selon la classification (logiciel d'aide à la décision, dispositif connecté, etc.), des obligations réglementaires strictes en santé peuvent s'appliquer avant toute mise sur le marché.",
            "legal_q_data": "Avez-vous mis en place un cadre de protection des données de santé (consentement patient, hébergement de données de santé certifié, anonymisation) ?",
            "product_q_poc": "Avez-vous testé votre solution avec des professionnels de santé ou patients pilotes dans un cadre encadré (étude clinique pilote, retour terrain) ?",
            "product_q_pmf": "Des établissements de santé, professionnels ou patients utilisent-ils votre solution de façon répétée et en tirent-ils un bénéfice mesurable ?",
            "financial_q_pmf": "Avez-vous des remboursements, conventionnements ou contrats B2B2C avec des structures de santé qui valident un modèle économique viable ?",
        },
    ),
    IndustryProfile(
        key="3", name="Security", family="software",
        overrides={
            "legal_q_regulatory": "Avez-vous réalisé un audit de sécurité externe ou des tests d'intrusion (pentest) sur votre solution ?",
            "legal_explanation_regulatory": "Dans la cybersécurité, la crédibilité technique passe souvent par des audits indépendants, des certifications (ISO 27001, SOC 2) et une gestion rigoureuse des vulnérabilités.",
            "legal_q_data": "Avez-vous une politique formelle de divulgation responsable des vulnérabilités et un processus de gestion des incidents ?",
            "product_q_poc": "Votre solution détecte/bloque-t-elle effectivement les menaces ciblées dans un environnement de test (red team, simulation d'attaque) ?",
            "product_q_pmf": "Des entreprises utilisent-elles votre solution en production sur des systèmes critiques, avec des SLA de détection/réponse respectés ?",
            "financial_q_scale": "Votre coût d'infrastructure (détection, monitoring 24/7, SOC) augmente-t-il moins vite que vos revenus à mesure que vous ajoutez des clients ?",
        },
    ),
    IndustryProfile(
        key="4", name="Fintech", family="software",
        overrides={
            "legal_q_regulatory": "Avez-vous obtenu ou engagé une demande d'agrément/licence auprès du régulateur financier compétent (banque centrale, autorité des marchés financiers, ou statut d'agent agréé) ?",
            "legal_explanation_regulatory": "Selon l'activité (paiement, crédit, gestion d'actifs, change), une licence ou un partenariat avec un établissement agréé est généralement obligatoire avant tout lancement commercial.",
            "legal_q_data": "Avez-vous mis en place les contrôles KYC/AML (connaissance client, lutte anti-blanchiment) requis pour votre activité ?",
            "product_q_poc": "Avez-vous testé les flux financiers réels (paiement, transfert, scoring) en environnement de bac à sable (sandbox réglementaire ou compte de test) ?",
            "product_q_pmf": "Des utilisateurs effectuent-ils des transactions financières réelles et répétées via votre plateforme ?",
            "financial_q_pmf": "Votre marge nette par transaction (après coûts de transaction, fraude, conformité) est-elle positive ou clairement modélisée pour le devenir ?",
        },
    ),
    IndustryProfile(
        key="5", name="Ad tech and creative tech", family="software",
        overrides={
            "legal_q_regulatory": "Votre solution est-elle conforme aux réglementations sur la publicité ciblée et le consentement (cookies, tracking, RGPD/ePrivacy) ?",
            "legal_explanation_regulatory": "Les plateformes publicitaires et créatives traitent souvent des données comportementales sensibles aux régulations sur la vie privée et la publicité en ligne.",
            "product_q_poc": "Avez-vous une démo fonctionnelle qui génère ou diffuse du contenu/des campagnes pour quelques clients pilotes ?",
            "product_q_pmf": "Vos clients annonceurs ou créateurs renouvellent-ils leurs campagnes/abonnements en raison de résultats mesurables (CTR, conversions, engagement) ?",
            "financial_q_pmf": "Votre coût d'acquisition client (CAC) est-il inférieur à la valeur vie client (LTV) générée par les campagnes/abonnements ?",
        },
    ),
    IndustryProfile(
        key="6", name="Communication services", family="software",
        overrides={
            "legal_q_regulatory": "Avez-vous vérifié si une autorisation d'opérateur de télécommunications ou un statut de fournisseur de service de communication est nécessaire dans vos marchés cibles ?",
            "product_q_poc": "Votre solution de communication (messagerie, voix, vidéo, API) fonctionne-t-elle de façon stable avec un volume d'utilisateurs test ?",
            "product_q_pmf": "Vos utilisateurs dépendent-ils de votre service de communication au quotidien pour leur activité professionnelle ou personnelle ?",
            "financial_q_scale": "Votre coût d'infrastructure réseau par utilisateur actif baisse-t-il à mesure que votre base d'utilisateurs augmente ?",
        },
    ),
    IndustryProfile(
        key="7", name="Advanced manufacturing and robotics", family="hardware",
        overrides={
            "legal_q_regulatory": "Avez-vous engagé les certifications de sécurité industrielle nécessaires (marquage CE machine, normes ISO robotique, certification électrique) ?",
            "legal_explanation_regulatory": "Les machines et robots destinés à un usage industriel ou public sont généralement soumis à des normes de sécurité strictes avant déploiement.",
            "product_q_poc": "Avez-vous un prototype fonctionnel testé en environnement contrôlé (atelier, banc d'essai) ?",
            "product_q_pmf": "Des industriels ont-ils intégré votre machine/robot dans leur ligne de production réelle avec des résultats mesurés ?",
            "financial_q_scale": "Avez-vous sécurisé une chaîne d'approvisionnement (composants, sous-traitants) capable de soutenir une production en série ?",
        },
    ),
    IndustryProfile(
        key="8", name="Real Estate Tech", family="software",
        overrides={
            "legal_q_regulatory": "Avez-vous vérifié les obligations légales liées à l'intermédiation immobilière (carte professionnelle, mandat, garantie financière) si applicable à votre modèle ?",
            "legal_explanation_regulatory": "Selon que vous faites de la simple mise en relation, de la gestion locative ou de la transaction, des statuts juridiques différents et obligatoires peuvent s'appliquer.",
            "product_q_poc": "Avez-vous une plateforme fonctionnelle testée avec un portefeuille pilote de biens ou de clients (agences, propriétaires, locataires) ?",
            "product_q_pmf": "Des agences, propriétaires ou locataires utilisent-ils votre solution de façon récurrente pour leurs transactions ou leur gestion ?",
            "financial_q_pmf": "Votre commission ou abonnement moyen par transaction/bien couvre-t-il vos coûts d'acquisition et d'exploitation ?",
        },
    ),
    IndustryProfile(
        key="9", name="Wellness", family="health_social",
        overrides={
            "legal_q_regulatory": "Avez-vous vérifié que vos allégations (bien-être, nutrition, activité physique) respectent la réglementation sur les allégations de santé et la publicité ?",
            "legal_explanation_regulatory": "Le secteur du bien-être est encadré par des règles strictes sur ce qu'on peut affirmer sans tomber dans l'allégation médicale non autorisée.",
            "product_q_poc": "Avez-vous testé votre programme/produit de bien-être avec un groupe pilote et recueilli des retours structurés ?",
            "product_q_pmf": "Vos utilisateurs constatent-ils des bénéfices perçus suffisants pour rester abonnés ou racheter régulièrement ?",
            "financial_q_pmf": "Votre taux de rétention/réabonnement est-il suffisant pour rentabiliser le coût d'acquisition de chaque utilisateur ?",
        },
    ),
    IndustryProfile(
        key="10", name="Travel Tech", family="ecommerce",
        overrides={
            "legal_q_regulatory": "Disposez-vous des garanties financières et licences requises pour la vente de voyages (garantie d'immatriculation agence de voyage, assurance responsabilité civile professionnelle) ?",
            "legal_explanation_regulatory": "La vente de prestations de voyage (vols, séjours, forfaits) est souvent soumise à un statut réglementé protégeant les consommateurs en cas de défaillance.",
            "product_q_poc": "Votre plateforme de réservation/voyage fonctionne-t-elle de bout en bout (recherche, paiement, confirmation) pour un nombre limité de destinations/partenaires ?",
            "product_q_pmf": "Vos voyageurs reviennent-ils réserver via votre plateforme pour de nouveaux voyages, ou la recommandent-ils ?",
            "financial_q_pmf": "Votre marge par réservation (après commissions partenaires, support client, remboursements) est-elle positive ?",
        },
    ),
    IndustryProfile(
        key="11", name="EdTech", family="software",
        overrides={
            "legal_q_regulatory": "Avez-vous vérifié les obligations spécifiques liées à l'utilisation de votre solution par des mineurs (consentement parental, protection des données des enfants) ?",
            "legal_explanation_regulatory": "Les solutions éducatives traitant des données d'élèves mineurs sont soumises à des protections renforcées de la vie privée dans la plupart des juridictions.",
            "product_q_poc": "Avez-vous testé votre contenu/plateforme pédagogique avec une classe pilote, un établissement ou un groupe d'apprenants ?",
            "product_q_pmf": "Les apprenants ou établissements constatent-ils des progrès mesurables et continuent-ils à utiliser/recommander votre solution ?",
            "financial_q_pmf": "Votre modèle (B2C abonnement, B2B établissement, B2G subvention) génère-t-il un revenu prévisible par utilisateur/établissement ?",
        },
    ),
    IndustryProfile(
        key="12", name="Agritech", family="hardware",
        overrides={
            "legal_q_regulatory": "Avez-vous vérifié la réglementation agricole applicable (autorisation de mise sur le marché pour intrants, normes sanitaires, certification bio/agréments) ?",
            "legal_explanation_regulatory": "Selon que votre produit touche aux intrants, à l'élevage, ou à l'alimentation, des homologations sanitaires et agricoles spécifiques sont généralement requises.",
            "product_q_poc": "Avez-vous testé votre solution (capteur, machine, intrant, logiciel) sur une parcelle ou exploitation pilote avec des résultats mesurés ?",
            "product_q_pmf": "Des exploitants agricoles adoptent-ils votre solution de façon répétée saison après saison ?",
            "financial_q_scale": "Votre coût de déploiement par hectare/exploitation baisse-t-il lorsque vous équipez davantage de parcelles ou clients ?",
        },
    ),
    IndustryProfile(
        key="13", name="Business Software and services", family="software",
        overrides={
            "legal_q_regulatory": "Avez-vous formalisé vos contrats clients (CGV/CGU B2B, SLA, clauses de protection des données) avant signature de vos premiers comptes ?",
            "product_q_poc": "Votre logiciel/service B2B fonctionne-t-il en conditions réelles chez un ou plusieurs clients pilotes ?",
            "product_q_pmf": "Vos clients B2B renouvellent-ils leur contrat/abonnement et étendent-ils leur usage (upsell, plus de licences) ?",
            "financial_q_pmf": "Votre revenu récurrent (MRR/ARR) croît-il de façon stable, avec un taux de désabonnement (churn) maîtrisé ?",
        },
    ),
    IndustryProfile(
        key="14", name="Environment", family="health_social",
        overrides={
            "legal_q_regulatory": "Avez-vous vérifié les certifications environnementales applicables (labels, normes d'émission, conformité aux réglementations environnementales locales) ?",
            "legal_explanation_regulatory": "Les solutions à impact environnemental sont souvent évaluées (et parfois exigées) sur la base de standards de mesure d'impact reconnus (GHG Protocol, labels officiels, etc.).",
            "product_q_poc": "Avez-vous mesuré et documenté l'impact environnemental réel de votre solution sur un déploiement pilote ?",
            "product_q_pmf": "Des clients ou partenaires adoptent-ils votre solution en partie grâce à un impact environnemental démontré et vérifiable ?",
            "financial_q_pmf": "Disposez-vous de financements verts, subventions ou crédits carbone qui consolident votre modèle économique ?",
        },
    ),
    IndustryProfile(
        key="15", name="Social Business", family="health_social",
        overrides={
            "legal_q_regulatory": "Avez-vous choisi/vérifié un statut juridique adapté à l'impact social visé (société à mission, agrément ESUS, association, coopérative) ?",
            "legal_explanation_regulatory": "Les entreprises à vocation sociale ont souvent accès à des statuts juridiques spécifiques qui conditionnent certains financements et obligations de gouvernance.",
            "product_q_poc": "Avez-vous testé votre solution/programme social auprès de la population cible et mesuré un premier impact ?",
            "product_q_pmf": "Le besoin social que vous adressez est-il confirmé par une adoption répétée et des retours qualitatifs/quantitatifs de la population bénéficiaire ?",
            "financial_q_pmf": "Votre modèle économique (subventions, vente de services, dons, mixte) couvre-t-il vos coûts opérationnels de façon prévisible ?",
        },
    ),
    IndustryProfile(
        key="16", name="Commerce and shopping", family="ecommerce",
        overrides={
            "legal_q_regulatory": "Avez-vous mis en place les mentions légales obligatoires de vente à distance (droit de rétractation, CGV, TVA applicable) ?",
            "product_q_poc": "Votre boutique/plateforme e-commerce permet-elle de réaliser des commandes et paiements réels de bout en bout ?",
            "product_q_pmf": "Vos clients repassent-ils commande (taux de réachat) ou recommandent-ils votre boutique/plateforme ?",
            "financial_q_pmf": "Votre marge brute par commande (après coût des marchandises, logistique, retours) est-elle positive ?",
        },
    ),
    IndustryProfile(
        key="17", name="Consumer product and services", family="ecommerce",
        overrides={
            "legal_q_regulatory": "Avez-vous vérifié les normes de sécurité/conformité produit applicables à votre catégorie (marquage CE, normes de sécurité jouets/cosmétiques/alimentaire, etc.) ?",
            "product_q_poc": "Avez-vous un produit/service fini que de vrais clients ont pu acheter ou utiliser au moins une fois ?",
            "product_q_pmf": "Vos clients rachètent-ils votre produit/service ou en parlent-ils positivement (bouche-à-oreille, avis) ?",
            "financial_q_pmf": "Votre marge unitaire après coûts de production/livraison est-elle positive sur chaque vente ?",
        },
    ),
]

INDUSTRIES_BY_KEY = {ind.key: ind for ind in INDUSTRIES}


# ==============================================================================
# SECTION 3: FAMILY FALLBACK TEXT BANK
# ==============================================================================
# When an industry doesn't override a slot, we fall back to one of four
# "family" phrasings. This keeps every industry deeply specific where it
# matters (regulation, product test, financial validation) while not
# requiring every single slot to be hand-written 17 times.

FAMILY_FALLBACKS = {
    "hardware": {
        "legal_q_regulatory": "Avez-vous identifié et engagé les certifications/homologations nécessaires pour votre produit physique (normes de sécurité, marquage réglementaire) ?",
        "legal_explanation_regulatory": "Les produits physiques sont souvent soumis à des normes de sécurité ou des homologations avant toute commercialisation.",
        "legal_q_data": "Avez-vous protégé votre propriété intellectuelle (brevet, dessin/modèle) sur les éléments innovants de votre matériel ?",
        "product_q_idea_adv": "Avez-vous un cahier des charges technique et un premier plan/schéma de conception ?",
        "product_q_poc": "Avez-vous construit un prototype physique qui fonctionne en conditions contrôlées ?",
        "product_q_pmf": "Des clients ou partenaires industriels utilisent-ils votre prototype/produit en conditions réelles avec des retours positifs répétés ?",
        "financial_q_poc": "Avez-vous chiffré le coût de fabrication d'une unité (BOM - bill of materials) ?",
        "financial_q_pmf": "Avez-vous des commandes fermes ou lettres d'intention qui valident une demande réelle pour votre produit ?",
        "financial_q_scale": "Avez-vous sécurisé une chaîne d'approvisionnement capable de soutenir une production à plus grande échelle ?",
        "team_q_poc": "Avez-vous une équipe technique (ingénierie, mécanique/électronique) capable de faire évoluer le prototype ?",
        "team_q_growth": "Avez-vous structuré des équipes dédiées à la qualité, la certification et les opérations industrielles ?",
    },
    "software": {
        "legal_q_regulatory": "Avez-vous vérifié les réglementations spécifiques à votre secteur logiciel (protection des données, conditions d'utilisation, propriété du code) ?",
        "legal_explanation_regulatory": "Même pour un produit numérique, des règles sectorielles (RGPD, droit de la consommation, conformité spécifique) s'appliquent souvent dès les premiers utilisateurs.",
        "legal_q_data": "Avez-vous une politique de confidentialité et des CGU conformes en place avant la collecte de données utilisateurs ?",
        "product_q_idea_adv": "Avez-vous une maquette interactive (wireframe/prototype Figma) testée auprès d'utilisateurs cibles ?",
        "product_q_poc": "Avez-vous une version codée fonctionnelle avec uniquement les fonctionnalités essentielles (MVP) ?",
        "product_q_pmf": "Vos utilisateurs utilisent-ils votre produit de façon régulière et le recommandent-ils à d'autres ?",
        "financial_q_poc": "Avez-vous estimé votre coût d'infrastructure (hébergement, API tierces) pour faire fonctionner le MVP ?",
        "financial_q_pmf": "Vos premiers clients payants génèrent-ils un revenu récurrent prévisible ?",
        "financial_q_scale": "Votre coût d'acquisition client (CAC) reste-t-il soutenable lorsque vous augmentez vos dépenses marketing/ventes ?",
        "team_q_poc": "Avez-vous une équipe technique capable de maintenir et faire évoluer le produit rapidement ?",
        "team_q_growth": "Avez-vous des équipes structurées par fonction (produit, ventes, support, ops) dans plusieurs pays ou marchés ?",
    },
    "health_social": {
        "legal_q_regulatory": "Avez-vous vérifié les réglementations spécifiques à votre activité (santé, social, environnement) avant le déploiement ?",
        "legal_explanation_regulatory": "Les secteurs à impact santé/social/environnemental sont souvent encadrés par des normes ou labels qui conditionnent la confiance des utilisateurs et partenaires.",
        "legal_q_data": "Avez-vous mis en place un cadre de consentement et de protection des données sensibles de vos utilisateurs/bénéficiaires ?",
        "product_q_idea_adv": "Avez-vous validé le besoin auprès de votre population cible (entretiens, enquêtes, étude terrain) ?",
        "product_q_poc": "Avez-vous testé une première version de votre solution/programme avec un groupe pilote ?",
        "product_q_pmf": "Votre population cible adopte-t-elle votre solution de façon répétée et en tire-t-elle un bénéfice constaté ?",
        "financial_q_poc": "Avez-vous estimé le coût de déploiement de votre solution/programme pilote ?",
        "financial_q_pmf": "Avez-vous un modèle de financement (vente, subvention, don, mixte) qui couvre vos coûts de fonctionnement ?",
        "financial_q_scale": "Votre modèle de financement est-il réplicable lorsque vous étendez votre solution à de nouvelles populations/zones ?",
        "team_q_poc": "Avez-vous une équipe (terrain, technique, ou les deux) capable de faire tourner le pilote ?",
        "team_q_growth": "Avez-vous structuré des équipes dédiées au suivi d'impact, aux partenariats et à l'expansion géographique ?",
    },
    "ecommerce": {
        "legal_q_regulatory": "Avez-vous mis en place les obligations légales de la vente (CGV, droit de rétractation, fiscalité applicable) ?",
        "legal_explanation_regulatory": "La vente de produits/services aux consommateurs est encadrée par des règles précises de protection du consommateur et de fiscalité.",
        "legal_q_data": "Avez-vous une politique de confidentialité conforme couvrant les données de paiement et de livraison de vos clients ?",
        "product_q_idea_adv": "Avez-vous validé la demande pour votre produit/service auprès de clients potentiels (précommandes, sondages, landing page) ?",
        "product_q_poc": "Pouvez-vous vendre et livrer/délivrer réellement votre produit/service de bout en bout, même à petite échelle ?",
        "product_q_pmf": "Vos clients rachètent-ils ou recommandent-ils votre produit/service ?",
        "financial_q_poc": "Avez-vous calculé votre coût unitaire (production, logistique, transaction) par vente ?",
        "financial_q_pmf": "Votre marge brute par vente est-elle positive après tous les coûts directs ?",
        "financial_q_scale": "Votre marge se maintient-elle ou s'améliore-t-elle lorsque vous augmentez vos volumes de vente ?",
        "team_q_poc": "Avez-vous une équipe capable de gérer la production/sourcing et la logistique à mesure que les ventes augmentent ?",
        "team_q_growth": "Avez-vous des équipes dédiées par marché/pays pour gérer ventes, logistique et support à grande échelle ?",
    },
}


# Slots that are truly universal (same wording regardless of industry family) —
# legal entity status, accounting basics, fundraising, hiring structure, etc.
UNIVERSAL_TEXT = {
    "legal_q_entity": "Quel est le statut juridique actuel de votre entreprise ?",
    "legal_explanation_entity": "Une structure juridique formelle (SARL, SAS, équivalent local) est généralement nécessaire pour signer des contrats, ouvrir un compte bancaire professionnel ou lever des fonds.",
    "legal_opt_entity_registered": "La société est officiellement immatriculée (registre de commerce, numéro fiscal actif).",
    "legal_opt_entity_in_progress": "Les statuts sont en cours de rédaction / l'immatriculation est en cours.",
    "legal_opt_entity_none": "Rien n'est encore déclaré, c'est un projet informel pour le moment.",

    "legal_q_ip": "Avez-vous protégé les éléments de propriété intellectuelle clés de votre projet (marque, nom de domaine, brevet, droits d'auteur) ?",
    "legal_explanation_ip": "Déposer sa marque et son nom de domaine tôt évite des conflits coûteux plus tard, surtout avant une phase de croissance.",
    "legal_opt_ip_full": "Oui, marque déposée et/ou brevet déposé, nom de domaine sécurisé.",
    "legal_opt_ip_partial": "Partiellement : nom de domaine réservé mais pas de dépôt de marque/brevet.",
    "legal_opt_ip_none": "Non, rien n'est protégé pour l'instant.",

    "legal_q_contracts": "Avez-vous des contrats écrits avec vos cofondateurs, employés clés et premiers clients/fournisseurs ?",
    "legal_explanation_contracts": "L'absence de contrats écrits (pacte d'associés, contrats de travail, CGV) est une des causes fréquentes de litiges entre cofondateurs ou avec des clients.",
    "legal_opt_contracts_full": "Oui, pacte d'associés et contrats principaux sont en place.",
    "legal_opt_contracts_partial": "Certains contrats existent mais il y a des zones non couvertes.",
    "legal_opt_contracts_none": "Non, tout fonctionne encore à l'oral / sur la confiance.",

    "financial_q_accounting": "Tenez-vous une comptabilité régulière (même basique) de vos dépenses et recettes ?",
    "financial_explanation_accounting": "Même en phase précoce, suivre ses dépenses évite les mauvaises surprises et prépare les futures levées de fonds ou déclarations fiscales.",
    "financial_opt_accounting_full": "Oui, comptabilité tenue par un expert-comptable ou un outil dédié, à jour.",
    "financial_opt_accounting_partial": "Je note les dépenses dans un tableau, sans suivi formel.",
    "financial_opt_accounting_none": "Non, je n'ai pas encore commencé à suivre cela.",

    "financial_q_funding": "Comment financez-vous actuellement votre activité ?",
    "financial_explanation_funding": "Le mode de financement (fonds propres, love money, subvention, levée de fonds) en dit long sur la maturité et le risque financier de votre projet.",
    "financial_opt_funding_bootstrap": "Sur mes fonds propres / love money, sans financement externe.",
    "financial_opt_funding_grant": "Grâce à des subventions, concours ou aides publiques.",
    "financial_opt_funding_seed": "J'ai levé une première ronde (friends & family, pré-seed, seed) auprès d'investisseurs.",
    "financial_opt_funding_vc": "Nous levons des tours en série A/B+ auprès de fonds de capital-risque.",

    "team_q_size": "Combien de personnes travaillent activement sur le projet aujourd'hui (associés inclus) ?",
    "team_explanation_size": "La taille et la structuration de l'équipe évoluent fortement entre chaque phase et influencent directement votre capacité à exécuter.",
    "team_opt_size_solo": "Juste moi, ou moi avec un cofondateur, à temps partiel.",
    "team_opt_size_small": "Une petite équipe (2 à 5 personnes) à temps plein.",
    "team_opt_size_mid": "Une équipe structurée par fonction (6 à 20 personnes).",
    "team_opt_size_large": "Une organisation de plus de 20 personnes avec plusieurs départements.",
}


# ==============================================================================
# SECTION 4: THE SHARED DEEP SPINE
# ==============================================================================
# build_industry_tree(profile) builds ONE complete tree for a given industry.
# The tree walks: LEGAL ENTITY -> TEAM SIZE -> [phase loop] where each phase
# checks PRODUCT, then LEGAL/REGULATORY, then FINANCIAL, before landing on a
# phase_result node or moving to the next phase's product question.
#
# This gives each industry run real depth (≈18-22 questions if you go all
# the way to GROWTH) while sharing one implementation.

def slot(profile: IndustryProfile, slot_id: str, default_text: str = None) -> str:
    """Resolve a slot: industry override -> family fallback -> universal -> default."""
    if slot_id in profile.overrides:
        return profile.overrides[slot_id]
    family_bank = FAMILY_FALLBACKS.get(profile.family, {})
    if slot_id in family_bank:
        return family_bank[slot_id]
    if slot_id in UNIVERSAL_TEXT:
        return UNIVERSAL_TEXT[slot_id]
    return default_text or f"[MISSING SLOT: {slot_id}]"


def build_industry_tree(profile: IndustryProfile) -> DecisionNode:
    p = profile.key  # short alias for unique node-id prefixing

    # ---------------------------------------------------------------
    # PHASE RESULT LEAVES (one per phase, industry name injected)
    # ---------------------------------------------------------------
    res_idea_start = DecisionNode(
        f"{p}_res_idea_start", phase="IDEATION",
        phase_result=(
            f"Phase : IDÉATION (Début) — Secteur {profile.name}.\n"
            "Votre idée n'est pas encore structurée. Prochaines actions concrètes : (1) rédigez "
            "une fiche problème en 1 page (qui souffre de quoi, pourquoi maintenant, pourquoi vous), "
            "(2) listez 3 alternatives déjà sur le marché et leur limite, (3) définissez votre cible "
            "prioritaire en 1 phrase. Ne passez pas à la validation avant d'avoir ces trois éléments."
        ),
    )
    res_idea_adv = DecisionNode(
        f"{p}_res_idea_adv", phase="IDEATION",
        phase_result=(
            f"Phase : IDÉATION (Avancée) — Secteur {profile.name}.\n"
            "Votre opportunité est identifiée. Avant de construire quoi que ce soit, validez vos "
            "hypothèses sur le terrain : menez 10 à 15 entretiens exploratoires avec votre cible, "
            "observez leurs comportements actuels, et vérifiez qu'ils cherchent activement une "
            "solution — et non juste qu'ils trouvent votre idée 'intéressante'."
        ),
    )
    res_market_validation = DecisionNode(
        f"{p}_res_market_validation", phase="MARKET_VALIDATION",
        phase_result=(
            f"Phase : VALIDATION MARCHÉ — Secteur {profile.name}.\n"
            "Vous testez la demande mais n'avez pas encore de confirmation solide. Prochaines "
            "actions : (1) définissez 1 hypothèse critique à invalider cette semaine, (2) créez "
            "le test le plus simple possible (landing page, pré-commande, pilote à 5 clients), "
            "(3) fixez un critère de succès binaire avant de lancer — pas après."
        ),
    )
    res_structuration = DecisionNode(
        f"{p}_res_structuration", phase="STRUCTURATION",
        phase_result=(
            f"Phase : STRUCTURATION — Secteur {profile.name}.\n"
            "La demande est prouvée, il faut maintenant poser les fondations. Priorités : "
            "(1) choisissez et formalisez votre structure juridique, (2) rédigez le pacte "
            "d'associés et les contrats clés, (3) documentez votre modèle économique avec des "
            "hypothèses chiffrées, (4) définissez les rôles et responsabilités de l'équipe. "
            "Ces éléments seront scrutés lors de tout financement."
        ),
    )
    res_fundraising = DecisionNode(
        f"{p}_res_fundraising", phase="FUNDRAISING",
        phase_result=(
            f"Phase : LEVÉE DE FONDS — Secteur {profile.name}.\n"
            "Votre structure est prête, vous cherchez des financements. Prochaines actions : "
            "(1) construisez votre pitch deck (problème, solution, marché, traction, équipe, "
            "besoin financier), (2) préparez un modèle financier sur 3 ans, (3) listez 20 "
            "financeurs ciblés par stade et secteur, (4) activez votre réseau pour des "
            "introductions — le cold outreach seul convertit rarement."
        ),
    )
    res_launch_planning = DecisionNode(
        f"{p}_res_launch_planning", phase="LAUNCH_PLANNING",
        phase_result=(
            f"Phase : PRÉPARATION AU LANCEMENT — Secteur {profile.name}.\n"
            "Le financement est sécurisé (ou la décision de lancer sans levée est prise). "
            "Prochaines actions : (1) finalisez le produit/service à un niveau commercialisable, "
            "(2) définissez votre stratégie de go-to-market (canal, message, prix, séquence de "
            "lancement), (3) préparez vos outils de vente et marketing, (4) fixez des objectifs "
            "de lancement mesurables sur 30/60/90 jours. L'exécution opérationnelle prime ici."
        ),
    )
    res_growth = DecisionNode(
        f"{p}_res_growth", phase="GROWTH",
        phase_result=(
            f"Phase : CROISSANCE — Secteur {profile.name}.\n"
            "Votre lancement est réussi et vous accélérez. Concentrez-vous sur : (1) identifier "
            "le levier de croissance principal (acquisition, rétention, ou expansion), (2) "
            "industrialiser les opérations pour ne pas que la qualité chute avec le volume, "
            "(3) structurer les équipes par fonction avec des OKRs clairs, (4) sécuriser les "
            "partenariats stratégiques qui multiplient la portée sans multiplier les coûts."
        ),
    )

    # ---------------------------------------------------------------
    # GROWTH PHASE
    # ---------------------------------------------------------------
    growth_team = DecisionNode(
        f"{p}_growth_team", phase="GROWTH", dimension="team",
        question="Avez-vous des équipes dédiées par fonction (acquisition, rétention, ops, produit) avec des responsables identifiés et des OKRs mesurables ?",
        explanation="En croissance, les fondateurs ne peuvent plus tout piloter directement. Des équipes autonomes par fonction avec des indicateurs clairs sont le signe d'une organisation scalable.",
    )
    growth_team.add_option(slot(profile, "team_opt_size_large", UNIVERSAL_TEXT["team_opt_size_large"]), res_growth)
    growth_team.add_option(slot(profile, "team_opt_size_mid", UNIVERSAL_TEXT["team_opt_size_mid"]), res_launch_planning)

    growth_financial = DecisionNode(
        f"{p}_growth_financial", phase="GROWTH", dimension="financial",
        question="Vos revenus récurrents, votre base clients et votre présence sur de nouveaux marchés progressent-ils tous les trois de façon mesurable sur les 3 derniers mois ?",
        explanation="Une vraie croissance se valide sur plusieurs indicateurs simultanément, pas uniquement sur la hausse du chiffre d'affaires.",
        allow_free_text=True,
    )
    growth_financial.add_option("Oui, les trois progressent de façon claire et documentée.", growth_team)
    growth_financial.add_option("Un ou deux progressent, mais pas les trois de façon systématique.", res_launch_planning)

    growth_legal = DecisionNode(
        f"{p}_growth_legal", phase="GROWTH", dimension="legal",
        question=slot(profile, "team_q_growth", FAMILY_FALLBACKS[profile.family]["team_q_growth"]),
        explanation="Une conformité réglementaire robuste sur chaque marché actif est un prérequis non-négociable pour lever des fonds ou signer des partenariats stratégiques.",
    )
    growth_legal.add_option("Oui, la conformité est gérée de façon autonome sur chaque marché où nous opérons.", growth_financial)
    growth_legal.add_option("Pas entièrement — certains marchés ou obligations réglementaires sont encore gérés au cas par cas.", res_launch_planning)

    # ---------------------------------------------------------------
    # LAUNCH_PLANNING PHASE
    # ---------------------------------------------------------------
    launch_team = DecisionNode(
        f"{p}_launch_team", phase="LAUNCH_PLANNING", dimension="team",
        question="Avez-vous les ressources humaines et opérationnelles en place pour exécuter votre lancement (commercial, marketing, support, livraison/déploiement) ?",
        explanation="Un lancement raté est souvent dû non pas au produit mais à l'absence de ressources pour gérer les premiers clients, les incidents et la communication simultanément.",
    )
    launch_team.add_option("Oui, les rôles clés du lancement sont couverts par des personnes dédiées.", growth_legal)
    launch_team.add_option("Partiellement — certaines fonctions critiques du lancement sont encore à pourvoir.", res_launch_planning)
    launch_team.add_option("Non, je lance avec les mêmes personnes qui font déjà tout le reste.", res_launch_planning)

    launch_financial = DecisionNode(
        f"{p}_launch_financial", phase="LAUNCH_PLANNING", dimension="financial",
        question="Avez-vous un budget de lancement défini, avec des objectifs de revenus ou d'acquisition sur les 30/60/90 premiers jours ?",
        explanation="Un lancement sans budget ni objectifs mesurables dégénère rapidement en dépenses non pilotées. Les 90 premiers jours post-lancement conditionnent la trajectoire des 12 mois suivants.",
        allow_free_text=True,
    )
    launch_financial.add_option("Oui, budget alloué et objectifs chiffrés définis pour les 90 premiers jours.", launch_team)
    launch_financial.add_option("Budget approximatif identifié mais objectifs de lancement non encore formalisés.", res_launch_planning)

    launch_legal = DecisionNode(
        f"{p}_launch_legal", phase="LAUNCH_PLANNING", dimension="legal",
        question=slot(profile, "legal_q_regulatory", FAMILY_FALLBACKS[profile.family]["legal_q_regulatory"]),
        explanation="Lancer sans conformité réglementaire complète peut exposer à des sanctions, des blocages opérationnels ou une perte de crédibilité auprès des premiers clients.",
    )
    launch_legal.add_option("Oui, toutes les obligations réglementaires nécessaires au lancement commercial sont remplies.", launch_financial)
    launch_legal.add_option("Non, certaines obligations réglementaires restent à finaliser avant de lancer.", res_launch_planning)

    launch_product = DecisionNode(
        f"{p}_launch_product", phase="LAUNCH_PLANNING", dimension="product",
        question="Avez-vous une stratégie de go-to-market définie : canal(aux) d'acquisition prioritaire(s), message de positionnement, politique tarifaire et séquence de lancement ?",
        explanation="Un bon produit sans stratégie de mise sur le marché ne se vend pas. Le go-to-market doit être aussi construit que le produit lui-même.",
        allow_free_text=True,
    )
    launch_product.add_option("Oui, notre GTM est documenté avec des canaux, un message, un prix et un plan de lancement.", launch_legal)
    launch_product.add_option("Partiellement — certains éléments du GTM sont définis mais pas encore formalisés ni testés.", res_launch_planning)
    launch_product.add_option("Non, nous allons lancer et ajuster le GTM en cours de route.", res_fundraising)

    # ---------------------------------------------------------------
    # FUNDRAISING PHASE
    # ---------------------------------------------------------------
    fundraising_team = DecisionNode(
        f"{p}_scale_team", phase="FUNDRAISING", dimension="team",
        question="Avez-vous une équipe avec les compétences clés couvertes (produit/tech, business/commercial, et idéalement finance/ops) pour exécuter votre plan de financement ET votre lancement ?",
        explanation="Les investisseurs évaluent en priorité l'équipe. Une équipe incomplète à ce stade rallonge les cycles de financement et fragilise le lancement qui suit.",
    )
    fundraising_team.add_option("Oui, les trois compétences clés sont couvertes par des personnes engagées à temps plein.", launch_product)
    fundraising_team.add_option("Partiellement — une ou plusieurs compétences clés manquent encore.", res_fundraising)
    fundraising_team.add_option("Non, je travaille seul ou avec une équipe encore très incomplète.", res_fundraising)

    fundraising_financial = DecisionNode(
        f"{p}_scale_financial", phase="FUNDRAISING", dimension="financial",
        question="Avez-vous un pitch deck finalisé, un modèle financier sur 3 ans, et au moins 5 rendez-vous investisseurs planifiés ou en cours ?",
        explanation="La levée de fonds est un funnel de vente : sans pitch deck, sans modèle financier et sans pipeline actif de financeurs, le processus ne peut pas avancer.",
        allow_free_text=True,
    )
    fundraising_financial.add_option("Oui, les trois éléments sont prêts et le pipeline investisseur est actif.", fundraising_team)
    fundraising_financial.add_option("En préparation — un ou deux éléments sont prêts mais pas encore les trois.", res_fundraising)

    fundraising_legal = DecisionNode(
        f"{p}_scale_legal", phase="FUNDRAISING", dimension="legal",
        question="Votre cap table, vos statuts et votre pacte d'associés sont-ils à jour, sans clauses bloquantes ni zones d'ombre sur la répartition des parts ?",
        explanation="Les investisseurs font une due diligence juridique systématique avant tout closing. Une cap table confuse ou un pacte inexistant peut bloquer une levée à la dernière minute.",
    )
    fundraising_legal.add_option("Oui, cap table propre, statuts à jour et pacte d'associés signé.", fundraising_financial)
    fundraising_legal.add_option("Partiellement — des ajustements ou clarifications sont encore nécessaires.", res_fundraising)
    fundraising_legal.add_option("Non, la documentation juridique n'est pas encore prête pour un investisseur.", res_fundraising)

    # ---------------------------------------------------------------
    # STRUCTURATION PHASE
    # ---------------------------------------------------------------
    structuration_team = DecisionNode(
        f"{p}_pmf_team", phase="STRUCTURATION", dimension="team",
        question="Combien de personnes travaillent activement sur le projet à temps plein, et les rôles sont-ils clairement définis ?",
        explanation="Une équipe structurée avec des rôles définis est un signal fort pour les partenaires et financeurs, et évite les conflits de périmètre qui bloquent l'exécution.",
    )
    structuration_team.add_option(UNIVERSAL_TEXT["team_opt_size_solo"], res_structuration)
    structuration_team.add_option(UNIVERSAL_TEXT["team_opt_size_small"], res_structuration)
    structuration_team.add_option(UNIVERSAL_TEXT["team_opt_size_mid"], fundraising_legal)
    structuration_team.add_option(UNIVERSAL_TEXT["team_opt_size_large"], growth_legal)

    structuration_financial = DecisionNode(
        f"{p}_pmf_financial", phase="STRUCTURATION", dimension="financial",
        question="Avez-vous un modèle économique documenté avec des hypothèses chiffrées sur vos revenus, vos coûts unitaires et votre point d'équilibre ?",
        explanation="'On monétisera plus tard' n'est pas un modèle économique. À ce stade, vous devez pouvoir répondre : comment gagnez-vous de l'argent, combien par unité, et à quel volume êtes-vous rentable ?",
        allow_free_text=True,
    )
    structuration_financial.add_option("Oui, le modèle est documenté avec des hypothèses chiffrées validées par de premières données terrain.", structuration_team)
    structuration_financial.add_option("En cours — les hypothèses existent mais n'ont pas encore été confrontées à des données réelles.", structuration_team)
    structuration_financial.add_option("Non, le modèle économique n'est pas encore formalisé ni chiffré.", res_market_validation)

    structuration_legal = DecisionNode(
        f"{p}_pmf_legal", phase="STRUCTURATION", dimension="legal",
        question="Avez-vous une entité légale immatriculée, un pacte d'associés signé et des contrats en place avec vos premiers clients ou fournisseurs clés ?",
        explanation="Ces trois éléments sont le minimum pour opérer en toute sécurité : sans entité légale, vous ne pouvez pas facturer ; sans pacte, les conflits entre fondateurs peuvent être fatals ; sans contrats, vous n'avez pas de protection.",
    )
    structuration_legal.add_option("Oui, entité créée, pacte d'associés signé et premiers contrats en place.", structuration_financial)
    structuration_legal.add_option("Partiellement — un ou deux éléments sont en cours de formalisation.", structuration_financial)
    structuration_legal.add_option("Non, tout fonctionne encore de façon informelle.", structuration_financial)

    structuration_engagement = DecisionNode(
        f"{p}_pmf_engagement", phase="STRUCTURATION", dimension="product",
        question=slot(profile, "product_q_pmf", FAMILY_FALLBACKS[profile.family]["product_q_pmf"]),
        explanation="On ne structure pas une idée — on structure une traction prouvée. Avant d'investir dans du juridique, du recrutement ou du financement, la demande doit être confirmée par des données réelles, pas des intentions.",
        allow_free_text=True,
    )
    structuration_engagement.add_option("Oui — au moins 5 clients/utilisateurs reviennent régulièrement et ont exprimé une volonté de payer ou de recommander.", structuration_legal)
    structuration_engagement.add_option("Quelques retours positifs mais pas encore de récurrence ni de signal fort d'achat.", res_market_validation)
    structuration_engagement.add_option("Pas encore de retours suffisants — nous cherchons toujours la bonne approche.", res_market_validation)

    # ---------------------------------------------------------------
    # MARKET_VALIDATION PHASE
    # ---------------------------------------------------------------
    market_validation_team = DecisionNode(
        f"{p}_poc_team", phase="MARKET_VALIDATION", dimension="team",
        question="Avez-vous au moins une personne dédiée à mener des entretiens clients et des expériences de validation (pas seulement au développement du produit) ?",
        explanation="La validation marché échoue souvent parce que toute l'équipe est sur le produit et personne n'est sur le terrain avec les clients. Au moins une personne doit avoir ce rôle explicitement.",
    )
    market_validation_team.add_option("Oui, au moins une personne est dédiée à la découverte client et aux tests terrain.", structuration_engagement)
    market_validation_team.add_option("Non, tout le monde est sur le produit — la validation se fait en parallèle sans rôle dédié.", structuration_engagement)

    market_validation_financial = DecisionNode(
        f"{p}_poc_financial", phase="MARKET_VALIDATION", dimension="financial",
        question="Avez-vous réalisé au minimum 10 entretiens qualitatifs avec votre cible, et au moins 1 expérience mesurable (landing page, pilote, pré-commande) ?",
        explanation="10 entretiens et 1 expérience sont le minimum pour avoir un signal exploitable. En dessous, vous opérez sur des intuitions, pas sur des données.",
    )
    market_validation_financial.add_option("Oui, au moins 10 entretiens réalisés ET une expérience avec des résultats mesurés.", market_validation_team)
    market_validation_financial.add_option("Moins de 10 entretiens ou aucune expérience mesurable encore réalisée.", market_validation_team)

    market_validation_legal = DecisionNode(
        f"{p}_poc_legal", phase="MARKET_VALIDATION", dimension="legal",
        question=slot(profile, "legal_q_regulatory", FAMILY_FALLBACKS[profile.family]["legal_q_regulatory"]),
        explanation=slot(profile, "legal_explanation_regulatory", FAMILY_FALLBACKS[profile.family]["legal_explanation_regulatory"]),
    )
    market_validation_legal.add_option("Oui, les contraintes réglementaires ont été identifiées et les démarches nécessaires sont en cours.", market_validation_financial)
    market_validation_legal.add_option("Non, nous n'avons pas encore analysé les contraintes réglementaires de notre secteur.", market_validation_financial)

    market_validation_status = DecisionNode(
        f"{p}_poc_status", phase="MARKET_VALIDATION", dimension="product",
        question=slot(profile, "product_q_poc", FAMILY_FALLBACKS[profile.family]["product_q_poc"]),
        explanation="La validation marché ne nécessite pas un produit fini : un prototype papier, une maquette Figma, ou même un service 'fait à la main' suffisent pour tester si des clients payeraient réellement.",
        allow_free_text=True,
    )
    market_validation_status.add_option("Nous avons des hypothèses mais aucune expérience concrète encore réalisée avec de vrais clients potentiels.", res_idea_adv)
    market_validation_status.add_option("Oui — un prototype ou pilote est en cours et nous recueillons des retours réels.", market_validation_legal)
    market_validation_status.add_option("La demande est confirmée par au moins 5 clients réguliers ou des pré-commandes signées.", structuration_engagement)

    # ---------------------------------------------------------------
    # IDEATION PHASE
    # ---------------------------------------------------------------
    idea_legal = DecisionNode(
        f"{p}_idea_legal", phase="IDEATION", dimension="legal",
        question="Avez-vous sécurisé les éléments de propriété intellectuelle de base : nom de domaine réservé, dépôt de marque engagé, et éventuellement brevet si applicable ?",
        explanation="En idéation, la PI se sécurise à faible coût. Attendre d'avoir un produit pour déposer sa marque expose à des conflits coûteux si un concurrent dépose le même nom entre-temps.",
    )
    idea_legal.add_option("Oui — nom de domaine réservé et dépôt de marque engagé (et brevet si pertinent).", market_validation_status)
    idea_legal.add_option("Partiellement — nom de domaine réservé mais dépôt de marque pas encore fait.", market_validation_status)
    idea_legal.add_option("Non — rien n'est encore protégé.", market_validation_status)

    idea_structured = DecisionNode(
        f"{p}_idea_structured", phase="IDEATION", dimension="product",
        question=slot(profile, "product_q_idea_adv", FAMILY_FALLBACKS[profile.family]["product_q_idea_adv"]),
        explanation="Structurer son idée, c'est répondre par écrit à trois questions : Quel problème précis résolvez-vous ? Pour qui exactement ? Pourquoi votre solution est meilleure que ce qui existe déjà ?",
        allow_free_text=True,
    )
    idea_structured.add_option("Oui — problème, cible et différenciation sont formalisés et documentés.", idea_legal)
    idea_structured.add_option("Non — c'est encore une intuition, rien n'est mis par écrit ni analysé.", res_idea_start)

    # ---------------------------------------------------------------
    # ROOT — overall product status, branches into the phase above it
    # ---------------------------------------------------------------
    q_main_product = DecisionNode(
        f"{p}_main_product", phase="ROOT", dimension="product",
        question=f"De manière globale, où en êtes-vous avec votre projet dans le secteur {profile.name} ?",
        explanation="Choisissez l'étape qui correspond le mieux à votre réalité aujourd'hui. Soyez honnête — une mauvaise auto-évaluation mène à de mauvaises priorités.",
    )
    q_main_product.add_option("Idéation — j'explore une idée, le problème et la cible ne sont pas encore clairement définis.", idea_structured)
    q_main_product.add_option("Validation marché — j'ai une hypothèse et je la teste auprès de vrais clients potentiels.", market_validation_status)
    q_main_product.add_option("Structuration — la demande est prouvée, je formalise le modèle, le juridique et l'équipe.", structuration_engagement)
    q_main_product.add_option("Levée de fonds — la structure est en place et je cherche des financements.", fundraising_legal)
    q_main_product.add_option("Préparation au lancement — le financement est sécurisé, je prépare l'entrée sur le marché.", launch_product)
    q_main_product.add_option("Croissance — le produit est lancé et je cherche à accélérer l'acquisition et l'expansion.", growth_legal)

    q_root_entity = DecisionNode(
        f"{p}_root_entity", phase="ROOT", dimension="legal",
        question=UNIVERSAL_TEXT["legal_q_entity"],
        explanation=UNIVERSAL_TEXT["legal_explanation_entity"],
    )
    q_root_entity.add_option(UNIVERSAL_TEXT["legal_opt_entity_registered"], q_main_product)
    q_root_entity.add_option(UNIVERSAL_TEXT["legal_opt_entity_in_progress"], q_main_product)
    q_root_entity.add_option(UNIVERSAL_TEXT["legal_opt_entity_none"], q_main_product)

    return q_root_entity  # this is the tree's root node


# ==============================================================================
# SECTION 5: JSON EXPORT ENGINE
# ==============================================================================

def export_tree_to_json(root_node: DecisionNode) -> str:
    """Recursively extracts a single tree into a clean JSON contract."""
    nodes_dict = {}

    def traverse(node):
        if node.node_id not in nodes_dict:
            nodes_dict[node.node_id] = node.to_dict()
            for _, next_node in node.options:
                traverse(next_node)

    traverse(root_node)
    return {
        "start_node_id": root_node.node_id,
        "nodes": nodes_dict,
    }


def export_all_industries_to_json(indent: int = 2) -> str:
    """Builds and exports every industry's tree into one JSON contract,
    keyed by industry id. This is the full frontend contract for all 17
    industries plus the menu metadata."""
    contract = {
        "industries": [
            {"key": ind.key, "name": ind.name, "family": ind.family}
            for ind in INDUSTRIES
        ],
        "trees": {},
    }
    for ind in INDUSTRIES:
        root = build_industry_tree(ind)
        contract["trees"][ind.key] = export_tree_to_json(root)
    return json.dumps(contract, indent=indent, ensure_ascii=False)


# ==============================================================================
# SECTION 6: INTERACTIVE APPLICATION
# ==============================================================================

def print_industry_menu():
    print("\n🏢 CATÉGORIE : Quel est le secteur de votre produit/entreprise ?")
    for ind in INDUSTRIES:
        print(f"  [{ind.key}] {ind.name}")


def run_interactive_classifier(classifier: LLMClassifier = None):
    classifier = classifier or DEFAULT_CLASSIFIER
    print("\n" + "=" * 80)
    print("   🚀 DÉCOUVREZ LA PHASE EXACTE DE VOTRE STARTUP")
    print("=" * 80)

    print_industry_menu()
    while True:
        choice = input("\n👉 Votre choix : ").strip()
        if choice in INDUSTRIES_BY_KEY:
            profile = INDUSTRIES_BY_KEY[choice]
            break
        print("❌ Choix invalide, veuillez choisir un numéro entre 1 et 17.")

    root_node = build_industry_tree(profile)
    final_phase, transcript = root_node.evaluate(classifier=classifier)

    print("\n" + "🌟" * 40)
    print("🏁 RÉSULTAT DE L'ANALYSE :")
    print(final_phase)
    print("🌟" * 40 + "\n")

    print("📝 Récapitulatif de vos réponses :")
    for entry in transcript:
        print(f"  - {entry}")

    return final_phase, transcript


# ==============================================================================
# SECTION 7: PERSONA TEST HARNESS
# ==============================================================================
# Canned synthetic founders used to regression-test the tree without a human
# typing answers. Each persona specifies:
#   - industry_key: which of the 17 industries to test
#   - answers: dict of node_id -> option index (int) OR "FREE:<text>" for a
#              free-text answer that gets routed through the classifier
#   - expected_phase: the phase tag we expect the persona to land on
#                      (IDEATION / MARKET_VALIDATION / STRUCTURATION / FUNDRAISING / LAUNCH_PLANNING / GROWTH)
#
# Because node ids are deterministic per industry (prefixed with the
# industry key, e.g. "4_main_product"), personas can be written generically
# and then have their industry-specific node ids generated automatically.

@dataclass
class Persona:
    name: str
    industry_key: str
    description: str
    answer_pattern: dict  # generic slot name -> answer, translated to node ids
    expected_phase: str


def _persona_answers_to_node_ids(industry_key: str, answer_pattern: dict) -> dict:
    """Translate a generic answer pattern (using short slot names) into the
    industry-prefixed node_id dict that evaluate_with_answers expects."""
    p = industry_key
    mapping = {
        "root_entity": f"{p}_root_entity",
        "main_product": f"{p}_main_product",
        "idea_structured": f"{p}_idea_structured",
        "idea_legal": f"{p}_idea_legal",
        "poc_status": f"{p}_poc_status",
        "poc_legal": f"{p}_poc_legal",
        "poc_financial": f"{p}_poc_financial",
        "poc_team": f"{p}_poc_team",
        "pmf_engagement": f"{p}_pmf_engagement",
        "pmf_legal": f"{p}_pmf_legal",
        "pmf_financial": f"{p}_pmf_financial",
        "pmf_team": f"{p}_pmf_team",
        "scale_legal": f"{p}_scale_legal",
        "scale_financial": f"{p}_scale_financial",
        "scale_team": f"{p}_scale_team",
        "launch_product": f"{p}_launch_product",
        "launch_legal": f"{p}_launch_legal",
        "launch_financial": f"{p}_launch_financial",
        "launch_team": f"{p}_launch_team",
        "growth_legal": f"{p}_growth_legal",
        "growth_financial": f"{p}_growth_financial",
        "growth_team": f"{p}_growth_team",
    }
    return {mapping[k]: v for k, v in answer_pattern.items() if k in mapping}


PERSONAS: list = [
    Persona(
        name="Amine — idée brute, Mobility",
        industry_key="1",
        description="Founder with just a concept for an electric scooter-sharing fleet, nothing on paper yet.",
        answer_pattern={
            "root_entity": 2,       # nothing declared
            "main_product": 0,      # still thinking
            "idea_structured": 1,   # not structured yet -> res_idea_start
        },
        expected_phase="IDEATION",
    ),
    Persona(
        name="Sarra — MVP codé, Fintech",
        industry_key="4",
        description="Fintech founder with a working payment MVP, tested in regulatory sandbox, no real paying users yet.",
        answer_pattern={
            "root_entity": 0,
            "main_product": 1,      # testing market validation
            "poc_status": 1,        # prototype in progress with real feedback
            "poc_legal": 0,         # KYC/AML steps engaged
            "poc_financial": 0,
            "poc_team": 0,
        },
        expected_phase="STRUCTURATION",  # poc_team routes to structuration_engagement next
    ),
    Persona(
        name="Yassine — traction réelle, EdTech",
        industry_key="11",
        description="EdTech founder with regular, repeat usage from a pilot school, decent recurring revenue, small team.",
        answer_pattern={
            "root_entity": 0,
            "main_product": 2,            # structuring
            "pmf_engagement": 0,          # demand confirmed, regular usage
            "pmf_legal": 0,               # legal structure in place
            "pmf_financial": 0,           # business model documented
            "pmf_team": 1,                # small team (2-5 people)
        },
        expected_phase="STRUCTURATION",
    ),
    Persona(
        name="Nour — prête à lancer, Advanced Manufacturing",
        industry_key="7",
        description="Hardware founder with funding secured, product ready, now preparing go-to-market and launch ops.",
        answer_pattern={
            "root_entity": 0,
            "main_product": 4,            # launch planning
            "launch_product": 0,          # GTM fully documented
            "launch_legal": 0,            # regulatory cleared for launch
            "launch_financial": 0,        # budget + 90-day objectives set
            "launch_team": 0,             # launch roles covered
        },
        expected_phase="GROWTH",          # launch_team -> growth_legal -> growth path
    ),
    Persona(
        name="Karim — levée bouclée, SaaS B2B",
        industry_key="13",
        description="B2B SaaS founder post-seed round, preparing product launch with GTM strategy in progress.",
        answer_pattern={
            "root_entity": 0,
            "main_product": 4,            # launch planning
            "launch_product": 1,          # GTM partially defined
        },
        expected_phase="LAUNCH_PLANNING",
    ),
    Persona(
        name="Wassim — expansion internationale, Communication services",
        industry_key="6",
        description="Comms platform founder raising a big international round, fully structured multi-country compliance team.",
        answer_pattern={
            "root_entity": 0,
            "main_product": 4,            # growing fast
            "growth_legal": 0,            # autonomous multi-market compliance
            "growth_financial": 0,        # clear measurable growth
            "growth_team": 0,             # large org (20+)
        },
        expected_phase="GROWTH",
    ),
    Persona(
        name="Free-text founder — Wellness, explains in own words",
        industry_key="9",
        description="Founder who prefers to explain their situation in free text rather than picking multiple choice; tests the LLM classifier routing.",
        answer_pattern={
            "root_entity": 0,
            "main_product": 1,
            "poc_status": "FREE:On a une appli de bien-être qui marche mais on a juste la fonctionnalité de base, rien de plus pour l'instant",
            "poc_legal": 1,
            "poc_financial": 1,
            "poc_team": 1,
        },
        expected_phase="STRUCTURATION",
    ),
]


def run_persona_tests(classifier: LLMClassifier = None, verbose: bool = True) -> bool:
    """Runs every persona through its industry tree using evaluate_with_answers
    (no stdin involved), and checks the resulting phase tag matches what's
    expected. Returns True if all personas pass.

    Defaults to DEMO_TEST_CLASSIFIER (a tiny rule-based stand-in tuned to
    this file's own persona sentences) so the free-text persona test is
    deterministic without requiring a real LLM API key. Pass your own
    `classifier` (wrapping a real `llm_classify_fn`) to test against an
    actual model instead.
    """
    classifier = classifier or DEMO_TEST_CLASSIFIER
    all_passed = True

    print("\n" + "=" * 80)
    print("🧪 PERSONA TEST HARNESS")
    print("=" * 80)

    for persona in PERSONAS:
        profile = INDUSTRIES_BY_KEY[persona.industry_key]
        root = build_industry_tree(profile)
        node_answers = _persona_answers_to_node_ids(persona.industry_key, persona.answer_pattern)

        result_text, transcript = root.evaluate_with_answers(node_answers, classifier=classifier)

        # The phase tag is embedded in the leaf node we ended on; recover it
        # by re-walking with the same answers but inspecting node.phase.
        ended_phase = _find_landing_phase(root, node_answers, classifier)

        passed = ended_phase == persona.expected_phase
        all_passed = all_passed and passed
        status = "✅ PASS" if passed else "❌ FAIL"

        if verbose:
            print(f"\n{status} — {persona.name}  [{profile.name}]")
            print(f"   {persona.description}")
            print(f"   Attendu: {persona.expected_phase}  |  Obtenu: {ended_phase}")
            print(f"   Résultat: {result_text.splitlines()[0]}")

    print("\n" + "-" * 80)
    print("✅ TOUS LES TESTS ONT RÉUSSI" if all_passed else "❌ CERTAINS TESTS ONT ÉCHOUÉ")
    print("-" * 80)
    return all_passed


def _find_landing_phase(root_node: DecisionNode, answers: dict, classifier: LLMClassifier) -> str:
    """Helper that walks the same path as evaluate_with_answers but returns
    the `.phase` tag of the leaf node landed on, for test assertions."""
    node = root_node
    while node.phase_result is None:
        ans = answers.get(node.node_id, 0)
        if isinstance(ans, str) and ans.startswith("FREE:"):
            free_text = ans[len("FREE:"):].strip()
            option_texts = [opt for opt, _ in node.options]
            idx = classifier.classify(free_text, option_texts, context={"question": node.question})
        else:
            idx = int(ans)
            idx = max(0, min(idx, len(node.options) - 1))
        node = node.options[idx][1]
    return node.phase


# ==============================================================================
# SECTION 8: MAIN ENTRY POINT
# ==============================================================================

def main():
    print("=== MENU PRINCIPAL ===")
    print("1. Lancer le questionnaire interactif (Terminal)")
    print("2. Exporter le contrat JSON pour l'équipe Frontend (les 17 secteurs)")
    print("3. Lancer les tests automatiques (personas)")
    print("4. Exporter le contrat JSON pour UN secteur uniquement")

    while True:
        mode = input("\n👉 Choisissez une option (1-4) : ").strip()

        if mode == "1":
            run_interactive_classifier()
            break

        elif mode == "2":
            print("\n" + "=" * 40)
            print("📦 FRONTEND JSON CONTRACT : 17 INDUSTRIES")
            print("=" * 40)
            print(export_all_industries_to_json())
            break

        elif mode == "3":
            ok = run_persona_tests()
            sys.exit(0 if ok else 1)

        elif mode == "4":
            print_industry_menu()
            key = input("\n👉 Secteur (1-17) : ").strip()
            if key in INDUSTRIES_BY_KEY:
                root = build_industry_tree(INDUSTRIES_BY_KEY[key])
                print(json.dumps(export_tree_to_json(root), indent=2, ensure_ascii=False))
            else:
                print("❌ Secteur invalide.")
            break

        else:
            print("❌ Choix invalide. Tapez un nombre entre 1 et 4.")


if __name__ == "__main__":
    main()
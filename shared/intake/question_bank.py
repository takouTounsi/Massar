"""Declarative question bank (FR/AR) plus probe and contradiction rules.

This is where the engine's intelligence lives. ``engine.py`` stays thin; all the
branching, probing and coherence knowledge is data here. Questions are bilingual
(``fr``/``ar``); rendering is driven by ``session.lang`` and the extractor copes
with mixed AR/FR free text.
"""

from __future__ import annotations

from shared.contracts.enums import IntakePhase, ProbeKind
from shared.intake.contracts import (
    Condition,
    ContradictionRule,
    FieldSpec,
    IntakeQuestion,
    ProbeRule,
)

# --- Questions (4-phase progressive disclosure) ---

QUESTIONS: list[IntakeQuestion] = [
    # Phase 1 — Foundation
    IntakeQuestion(
        id="q_sector",
        phase=IntakePhase.FOUNDATION,
        text={
            "fr": "Dans quel secteur évoluez-vous, et que fait votre projet ?",
            "ar": "في أي قطاع تعمل، وماذا يفعل مشروعك؟",
        },
        targets=["sector"],
        extract_fields=[
            FieldSpec(
                name="sector",
                type="enum",
                options=["fintech", "agri-food", "ess", "saas", "industry", "services", "other"],
                description={"fr": "Secteur principal", "ar": "القطاع الرئيسي"},
            ),
        ],
    ),
    IntakeQuestion(
        id="q_declared_stage",
        phase=IntakePhase.FOUNDATION,
        text={
            "fr": "À quel stade estimez-vous être aujourd'hui ?",
            "ar": "في أي مرحلة تعتقد أنك اليوم؟",
        },
        captures_declared_stage=True,
        extract_fields=[
            FieldSpec(
                name="declared_stage",
                type="enum",
                options=["S1", "S2", "S3", "S4", "S5", "S6"],
                description={"fr": "Auto-évaluation du stade", "ar": "التقييم الذاتي للمرحلة"},
            ),
        ],
    ),
    IntakeQuestion(
        id="q_idea",
        phase=IntakePhase.FOUNDATION,
        text={
            "fr": "Quel problème résolvez-vous et depuis quand travaillez-vous dessus ?",
            "ar": "ما المشكلة التي تحلها ومنذ متى تعمل عليها؟",
        },
        targets=["has_prototype", "founding_date"],
        extract_fields=[
            FieldSpec(name="has_prototype", type="boolean",
                      description={"fr": "Prototype/MVP existant", "ar": "وجود نموذج أولي"}),
            FieldSpec(name="founding_date", type="date",
                      description={"fr": "Date de démarrage", "ar": "تاريخ البدء"}),
        ],
    ),
    IntakeQuestion(
        id="q_innovation",
        phase=IntakePhase.FOUNDATION,
        text={
            "fr": "Qu'est-ce qui rend votre solution nouvelle ou différente "
                  "sur le marché tunisien ?",
            "ar": "ما الذي يجعل حلّك جديدًا أو مختلفًا في السوق التونسية؟",
        },
        targets=["innovation_level"],
        extract_fields=[
            FieldSpec(
                name="innovation_level",
                type="enum",
                options=["high", "medium", "low"],
                description={
                    "fr": "Degré de nouveauté/différenciation: high (rupture/nouveau "
                          "sur le marché), medium (amélioration notable), low (offre "
                          "déjà répandue)",
                    "ar": "درجة الجِدّة/التمايز: high (ابتكار جديد)، medium (تحسين "
                          "ملحوظ)، low (عرض شائع)",
                },
            ),
        ],
    ),
    # Phase 2 — Market & Clients
    IntakeQuestion(
        id="q_revenue_model",
        phase=IntakePhase.MARKET_CLIENTS,
        text={
            "fr": "Comment gagnez-vous de l'argent ? Votre modèle de revenus "
                  "est-il défini et cohérent ?",
            "ar": "كيف تجني المال؟ هل نموذج إيراداتك واضح ومتماسك؟",
        },
        targets=["revenue_model_clarity"],
        extract_fields=[
            FieldSpec(
                name="revenue_model_clarity",
                type="enum",
                options=["clear", "partial", "unclear"],
                description={
                    "fr": "Clarté du modèle de revenus: clear (défini et testé), "
                          "partial (idée mais non validée), unclear (pas de modèle "
                          "défini)",
                    "ar": "وضوح نموذج الإيرادات: clear (محدد ومُختبَر)، partial (فكرة "
                          "غير مؤكدة)، unclear (غير محدد)",
                },
            ),
        ],
    ),
    IntakeQuestion(
        id="q_problem_validation",
        phase=IntakePhase.MARKET_CLIENTS,
        text={
            "fr": "Avez-vous validé le problème auprès de clients potentiels (entretiens, tests) ?",
            "ar": "هل تحققت من المشكلة مع عملاء محتملين (مقابلات، اختبارات)؟",
        },
        targets=["problem_validated", "documented_interviews"],
        extract_fields=[
            FieldSpec(name="problem_validated", type="boolean",
                      description={"fr": "Problème validé", "ar": "تم التحقق من المشكلة"}),
            FieldSpec(name="documented_interviews", type="integer",
                      description={"fr": "Nombre d'entretiens documentés",
                                   "ar": "عدد المقابلات الموثقة"}),
        ],
    ),
    IntakeQuestion(
        id="q_clients",
        phase=IntakePhase.MARKET_CLIENTS,
        text={
            "fr": "Avez-vous des clients qui paient aujourd'hui ? Combien, et est-ce récurrent ?",
            "ar": "هل لديك عملاء يدفعون اليوم؟ كم عددهم، وهل هو متكرر؟",
        },
        targets=["paying_customers", "claims_traction", "recurring_revenue"],
        extract_fields=[
            FieldSpec(name="paying_customers", type="integer",
                      description={"fr": "Nombre de clients payants",
                                   "ar": "عدد العملاء الدافعين"}),
            FieldSpec(name="claims_traction", type="boolean",
                      description={"fr": "Affirme avoir de la traction", "ar": "يدعي وجود زخم"}),
            FieldSpec(name="recurring_revenue", type="boolean",
                      description={"fr": "Revenus récurrents", "ar": "إيرادات متكررة"}),
        ],
    ),
    IntakeQuestion(
        id="q_market_size",
        phase=IntakePhase.MARKET_CLIENTS,
        text={
            "fr": "Avez-vous estimé la taille de votre marché ?",
            "ar": "هل قدّرت حجم سوقك؟",
        },
        targets=["market_size_known"],
        extract_fields=[
            FieldSpec(name="market_size_known", type="boolean",
                      description={"fr": "Taille de marché estimée", "ar": "تقدير حجم السوق"}),
        ],
    ),
    # Phase 3 — Model & Legal
    IntakeQuestion(
        id="q_legal_entity",
        phase=IntakePhase.MODEL_LEGAL,
        text={
            "fr": "Votre entreprise est-elle enregistrée (RNE) ? Sous quelle forme juridique ?",
            "ar": "هل شركتك مسجلة (RNE)؟ وما هو شكلها القانوني؟",
        },
        targets=["has_legal_entity", "legal_form", "formalization_status"],
        extract_fields=[
            FieldSpec(name="has_legal_entity", type="boolean",
                      description={"fr": "Immatriculée au RNE", "ar": "مسجلة في RNE"}),
            FieldSpec(name="legal_form", type="enum",
                      options=["ENTREPRISE_INDIVIDUELLE", "SUARL", "SARL", "SA"],
                      description={"fr": "Forme juridique", "ar": "الشكل القانوني"}),
            FieldSpec(name="formalization_status", type="enum",
                      options=["informal", "in_progress", "formalized"],
                      description={"fr": "Statut de formalisation", "ar": "حالة التشكيل القانوني"}),
        ],
    ),
    IntakeQuestion(
        id="q_invoices",
        phase=IntakePhase.MODEL_LEGAL,
        text={
            "fr": "Émettez-vous des factures avec TVA pour vos ventes ?",
            "ar": "هل تصدر فواتير مع ضريبة القيمة المضافة لمبيعاتك؟",
        },
        targets=["invoices_with_vat"],
        extract_fields=[
            FieldSpec(name="invoices_with_vat", type="boolean",
                      description={"fr": "Factures avec TVA", "ar": "فواتير مع TVA"}),
        ],
    ),
    IntakeQuestion(
        id="q_fiscal",
        phase=IntakePhase.MODEL_LEGAL,
        text={
            "fr": "Êtes-vous à jour de vos obligations fiscales (TVA) et sociales (CNSS) ?",
            "ar": "هل أنت ملتزم بالتزاماتك الجبائية (TVA) والاجتماعية (CNSS)؟",
        },
        targets=["has_tva", "has_cnss"],
        preconditions=[Condition(field="has_legal_entity", op="truthy")],
        extract_fields=[
            FieldSpec(name="has_tva", type="boolean",
                      description={"fr": "Enregistré à la TVA", "ar": "مسجل في TVA"}),
            FieldSpec(name="has_cnss", type="boolean",
                      description={"fr": "Affilié à la CNSS", "ar": "منخرط في CNSS"}),
        ],
    ),
    # Phase 4 — Finance & Team
    IntakeQuestion(
        id="q_revenue",
        phase=IntakePhase.FINANCE_TEAM,
        text={
            "fr": "Quel est votre chiffre d'affaires mensuel approximatif ?",
            "ar": "ما هو رقم معاملاتك الشهري التقريبي؟",
        },
        targets=["monthly_revenue"],
        extract_fields=[
            FieldSpec(name="monthly_revenue", type="number",
                      description={"fr": "CA mensuel (TND)", "ar": "رقم المعاملات الشهري"}),
        ],
    ),
    IntakeQuestion(
        id="q_team",
        phase=IntakePhase.FINANCE_TEAM,
        text={
            "fr": "Combien de personnes composent votre équipe ?",
            "ar": "كم عدد أعضاء فريقك؟",
        },
        targets=["team_size"],
        extract_fields=[
            FieldSpec(name="team_size", type="integer",
                      description={"fr": "Taille de l'équipe", "ar": "حجم الفريق"}),
        ],
    ),
    IntakeQuestion(
        id="q_automation",
        phase=IntakePhase.FINANCE_TEAM,
        text={
            "fr": "Quelle part de vos processus clés est automatisée ?",
            "ar": "ما نسبة عملياتك الرئيسية المؤتمتة؟",
        },
        targets=["process_automation_level"],
        extract_fields=[
            FieldSpec(name="process_automation_level", type="number",
                      description={"fr": "Niveau d'automatisation (0-1)", "ar": "مستوى الأتمتة"}),
        ],
    ),
    # --- Probe questions (queued by probe_engine, never freely selected) ---
    IntakeQuestion(
        id="probe_traction_evidence",
        phase=IntakePhase.MARKET_CLIENTS,
        is_probe=True,
        text={
            "fr": "Vous mentionnez des clients : pouvez-vous le prouver "
                  "par des factures (avec TVA) ?",
            "ar": "تذكر وجود عملاء: هل يمكنك إثبات ذلك بفواتير (مع TVA)؟",
        },
        targets=["invoices_with_vat"],
        extract_fields=[
            FieldSpec(name="invoices_with_vat", type="boolean",
                      description={"fr": "Factures avec TVA disponibles",
                                   "ar": "فواتير مع TVA متوفرة"}),
        ],
    ),
    IntakeQuestion(
        id="probe_clarify_formalization",
        phase=IntakePhase.MODEL_LEGAL,
        is_probe=True,
        text={
            "fr": "Vous avez des clients récurrents mais pas d'entité légale "
                  "— comment facturez-vous ?",
            "ar": "لديك عملاء متكررون لكن دون كيان قانوني — كيف تصدر الفواتير؟",
        },
        targets=["has_legal_entity", "formalization_status"],
        extract_fields=[
            FieldSpec(name="has_legal_entity", type="boolean",
                      description={"fr": "Possède une entité légale", "ar": "يملك كيانًا قانونيًا"}),
            FieldSpec(name="formalization_status", type="enum",
                      options=["informal", "in_progress", "formalized"],
                      description={"fr": "Statut de formalisation", "ar": "حالة التشكيل"}),
        ],
    ),
    # Sector module — fintech
    IntakeQuestion(
        id="probe_fintech_license",
        phase=IntakePhase.MODEL_LEGAL,
        is_probe=True,
        text={
            "fr": "En fintech : disposez-vous d'un agrément BCT / licence réglementaire ?",
            "ar": "في الفينتك: هل لديك ترخيص من البنك المركزي / رخصة تنظيمية؟",
        },
        targets=["regulatory_license"],
        extract_fields=[
            FieldSpec(name="regulatory_license", type="boolean",
                      description={"fr": "Agrément réglementaire", "ar": "ترخيص تنظيمي"}),
        ],
    ),
    # Sector module — agri-food
    IntakeQuestion(
        id="probe_agri_cold_chain",
        phase=IntakePhase.MODEL_LEGAL,
        is_probe=True,
        text={
            "fr": "En agroalimentaire : avez-vous une chaîne du froid et "
                  "des certifications sanitaires ?",
            "ar": "في الصناعات الغذائية: هل لديك سلسلة تبريد وشهادات صحية؟",
        },
        targets=["cold_chain", "food_certification", "seasonality"],
        extract_fields=[
            FieldSpec(name="cold_chain", type="boolean",
                      description={"fr": "Chaîne du froid", "ar": "سلسلة التبريد"}),
            FieldSpec(name="food_certification", type="boolean",
                      description={"fr": "Certification sanitaire", "ar": "شهادة صحية"}),
            FieldSpec(name="seasonality", type="boolean",
                      description={"fr": "Activité saisonnière", "ar": "نشاط موسمي"}),
        ],
    ),
    # Sector module — ESS (social & solidarity economy)
    IntakeQuestion(
        id="probe_ess_impact",
        phase=IntakePhase.FINANCE_TEAM,
        is_probe=True,
        text={
            "fr": "En ESS : quel est votre impact mesuré et combien "
                  "de bénéficiaires touchez-vous ?",
            "ar": "في الاقتصاد الاجتماعي: ما هو أثرك المقاس وكم عدد المستفيدين؟",
        },
        targets=["impact_measured", "beneficiary_count"],
        extract_fields=[
            FieldSpec(name="impact_measured", type="boolean",
                      description={"fr": "Impact mesuré", "ar": "الأثر مقاس"}),
            FieldSpec(name="beneficiary_count", type="integer",
                      description={"fr": "Nombre de bénéficiaires", "ar": "عدد المستفيدين"}),
        ],
    ),
]

QUESTIONS_BY_ID: dict[str, IntakeQuestion] = {q.id: q for q in QUESTIONS}


# --- Probe rules ---

PROBE_RULES: list[ProbeRule] = [
    # EVIDENCE: a traction claim without documentation -> demand the artifact.
    ProbeRule(
        id="rule_traction_evidence",
        kind=ProbeKind.EVIDENCE,
        trigger=[
            Condition(field="claims_traction", op="truthy"),
            Condition(field="invoices_with_vat", op="status_in",
                      value=["UNVERIFIED", "MISSING", "CONTRADICTED"], on="status"),
        ],
        ask="probe_traction_evidence",
    ),
    # SECTOR: inject a regulatory module based on the declared sector.
    ProbeRule(
        id="rule_sector_fintech",
        kind=ProbeKind.SECTOR,
        trigger=[Condition(field="sector", op="eq", value="fintech")],
        inject=["probe_fintech_license"],
    ),
    ProbeRule(
        id="rule_sector_agri",
        kind=ProbeKind.SECTOR,
        trigger=[Condition(field="sector", op="eq", value="agri-food")],
        inject=["probe_agri_cold_chain"],
    ),
    ProbeRule(
        id="rule_sector_ess",
        kind=ProbeKind.SECTOR,
        trigger=[Condition(field="sector", op="eq", value="ess")],
        inject=["probe_ess_impact"],
    ),
    # STAGE_SKIP: strong early evidence marks downstream basics as inferred.
    # SARL + invoices -> no need to ask "do you have an idea / a prototype".
    ProbeRule(
        id="rule_skip_basics",
        kind=ProbeKind.STAGE_SKIP,
        trigger=[
            Condition(field="has_legal_entity", op="truthy"),
            Condition(field="invoices_with_vat", op="truthy"),
        ],
        mark_inferred=["q_idea", "q_problem_validation"],
        confirm_fields=["problem_validated", "has_prototype"],
    ),
]


# --- Contradiction rules (Tunisian regulatory coherence) ---

CONTRADICTION_RULES: list[ContradictionRule] = [
    # Recurring paying clients but no legal entity -> incoherent, clarify.
    ContradictionRule(
        id="contradiction_recurring_no_entity",
        when=[
            Condition(field="recurring_revenue", op="truthy"),
            Condition(field="has_legal_entity", op="falsy"),
        ],
        contradicted_field="formalization_status",
        clarification_probe="probe_clarify_formalization",
        reason={
            "fr": "Des revenus récurrents sans entité légale sont incohérents "
                  "au regard du droit tunisien.",
            "ar": "إيرادات متكررة دون كيان قانوني أمر غير متسق مع القانون التونسي.",
        },
    ),
    # Claims TVA compliance but no legal entity -> impossible.
    ContradictionRule(
        id="contradiction_tva_no_entity",
        when=[
            Condition(field="has_tva", op="truthy"),
            Condition(field="has_legal_entity", op="falsy"),
        ],
        contradicted_field="has_tva",
        clarification_probe="probe_clarify_formalization",
        reason={
            "fr": "Être assujetti à la TVA suppose une entité légale immatriculée.",
            "ar": "الخضوع لـ TVA يفترض وجود كيان قانوني مسجل.",
        },
    ),
    # Invoices with VAT but informal status -> incoherent.
    ContradictionRule(
        id="contradiction_invoices_informal",
        when=[
            Condition(field="invoices_with_vat", op="truthy"),
            Condition(field="has_legal_entity", op="falsy"),
        ],
        contradicted_field="invoices_with_vat",
        clarification_probe="probe_clarify_formalization",
        reason={
            "fr": "Émettre des factures avec TVA sans entité légale est incohérent.",
            "ar": "إصدار فواتير مع TVA دون كيان قانوني غير متسق.",
        },
    ),
]

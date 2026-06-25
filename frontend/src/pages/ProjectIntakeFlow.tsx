import { useMutation, useQuery } from "@tanstack/react-query";
import { AlertTriangle, Check, ChevronRight, Loader2, Send, ShieldCheck, Sparkles } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  AdaptiveQuestion,
  Contradiction,
  Diagnosis,
  answerSession,
  applyPml,
  getDiagnosis,
  getSessionState,
  startSession
} from "../api/adaptiveClient";
import {
  ClassifierStep,
  ClassifierTranscriptEntry,
  answerClassification,
  listIndustries,
  startClassification
} from "../api/classification";
import { LoadingState } from "../components/LoadingState";
import { STAGE_ORDER } from "../lib/diagnosis";
import { useI18n } from "../i18n/useI18n";

// Orchestrates the real chain for a freshly created project:
//   1. Classification (PML) — the founder's PERCEIVED maturity self-assessment.
//   2. Hand the terminal PML payload to the Adaptive Intake Engine via /pml
//      (declared/perceived side ONLY — never the evidence ledger).
//   3. Adaptive intake — evidence-driven Q&A that VERIFIES the claim.
//   4. Diagnosis — maturity + scoring over the evidence ledger.
// Every step is a real backend call; nothing is faked. (Integration sourced
// from commit 938c5fd; presentation re-skinned to match commit aa9746e.)
type Phase = "industry" | "classify" | "linking" | "intake";

type Turn = { question: string; answer: string };

export function ProjectIntakeFlow() {
  const { projectId = "" } = useParams();
  const { t, label, language, dir } = useI18n();

  const [phase, setPhase] = useState<Phase>("industry");

  // ── Classification (PML) state ──
  const [industryKey, setIndustryKey] = useState<string>("");
  const [step, setStep] = useState<ClassifierStep | null>(null);
  const [classifierTranscript, setClassifierTranscript] = useState<ClassifierTranscriptEntry[]>([]);
  const [classifyInput, setClassifyInput] = useState<string>("");

  // ── Adaptive intake state ──
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [question, setQuestion] = useState<AdaptiveQuestion | null>(null);
  const [answer, setAnswer] = useState("");
  const [transcript, setTranscript] = useState<Turn[]>([]);
  const [ready, setReady] = useState(false);
  const [firedProbes, setFiredProbes] = useState<string[]>([]);
  const [contradictions, setContradictions] = useState<Contradiction[]>([]);
  const [showSuccess, setShowSuccess] = useState(false);

  const industriesQuery = useQuery({ queryKey: ["industries"], queryFn: listIndustries });

  const stateQuery = useQuery({
    queryKey: ["adaptive-state", sessionId],
    queryFn: () => getSessionState(sessionId as string),
    enabled: Boolean(sessionId)
  });
  const diagnosisQuery = useQuery<Diagnosis>({
    queryKey: ["adaptive-diagnosis", sessionId],
    queryFn: () => getDiagnosis(sessionId as string),
    enabled: Boolean(sessionId) && ready
  });

  // Begin the PML questionnaire for the chosen industry.
  const startClassify = useMutation({
    mutationFn: () => startClassification(industryKey),
    onSuccess: (first) => {
      setStep(first);
      setClassifierTranscript([]);
      setClassifyInput("");
      setPhase("classify");
    }
  });

  // Once the classifier reaches its terminal phase, hand that PML payload to the
  // intake engine: start a session tied to THIS project, then post the raw PML.
  const link = useMutation({
    mutationFn: async (terminal: ClassifierStep) => {
      const start = await startSession(language, projectId);
      // The whole terminal payload (carries `phase` + `transcript`) is mapped by
      // the intake service's adapter into declared_stage — perceived side only.
      await applyPml(start.session_id, terminal as unknown as Record<string, unknown>);
      return start;
    },
    onSuccess: (start) => {
      setSessionId(start.session_id);
      setQuestion(start.first_question);
      setTranscript([]);
      setReady(false);
      setPhase("intake");
    }
  });

  // One classifier turn: record the answer locally (the backend expects the
  // running transcript), submit, advance — or, if terminal, link to intake.
  const answerClassify = useMutation({
    mutationFn: (chosen: { index?: number; text?: string; answerText: string }) => {
      if (!step) throw new Error("No active classification step");
      const entry: ClassifierTranscriptEntry = {
        node_id: step.node_id,
        question: step.question ?? "",
        chosen_answer_text: chosen.answerText
      };
      const nextTranscript = [...classifierTranscript, entry];
      setClassifierTranscript(nextTranscript);
      return answerClassification({
        session_industry_key: step.session_industry_key,
        session_id: step.session_id,
        node_id: step.node_id,
        selected_option_index: chosen.index ?? null,
        free_text: chosen.text ?? null,
        transcript_so_far: nextTranscript
      });
    },
    onSuccess: (next) => {
      setClassifyInput("");
      if (next.is_terminal) {
        setStep(next);
        setPhase("linking");
        link.mutate(next);
      } else {
        setStep(next);
      }
    }
  });

  // One adaptive intake turn.
  const submit = useMutation({
    mutationFn: () => answerSession(sessionId as string, (question as AdaptiveQuestion).id, answer),
    onSuccess: (data) => {
      setTranscript((prev) => [
        ...prev,
        { question: question?.text[language] ?? question?.text.fr ?? "", answer }
      ]);
      setShowSuccess(true);
      setTimeout(() => setShowSuccess(false), 800);
      setAnswer("");
      setQuestion(data.next_question);
      setReady(data.diagnostic_ready);
      setFiredProbes(data.fired_probes);
      setContradictions(data.contradictions);
      stateQuery.refetch();
    }
  });

  // ── Chain progress stepper (re-skin of aa9746e's progress header panel) ──
  const stepIndex = phase === "industry" || phase === "classify" ? 0 : phase === "linking" ? 1 : ready ? 2 : 1;
  const chainSteps = [
    { n: 1, title: t("intake.flowStepClassify"), done: stepIndex > 0, active: stepIndex === 0 },
    { n: 2, title: t("intake.flowStepIntake"), done: stepIndex > 1, active: stepIndex === 1 },
    { n: 3, title: t("intake.flowStepDiagnosis"), done: false, active: stepIndex === 2 }
  ];
  const chainPct = ready ? 100 : ((stepIndex + 0.5) / 3) * 100;

  const ProgressHeader = (
    <div className="panel p-4">
      <div className="mb-3 flex flex-wrap items-center gap-3">
        {chainSteps.map((s, i) => (
          <div key={s.n} className="flex items-center gap-2">
            <span
              className={`grid h-6 w-6 place-items-center rounded-full text-xs font-semibold ${
                s.done
                  ? "bg-evidence-600 text-white"
                  : s.active
                  ? "bg-navy-600 text-white"
                  : "bg-navy-100 text-ink-400"
              }`}
            >
              {s.done ? <Check size={13} /> : s.n}
            </span>
            <span className={`text-sm ${s.active || s.done ? "text-ink-700" : "text-ink-400"}`}>{s.title}</span>
            {i < chainSteps.length - 1 && <ChevronRight size={15} className="text-navy-200" />}
          </div>
        ))}
        <span className="ms-auto text-xs font-medium tabular-nums text-ink-400">{Math.round(chainPct)}%</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-navy-100">
        <div
          className="h-full rounded-full bg-evidence-600 transition-all duration-700"
          style={{ width: `${chainPct}%` }}
        />
      </div>
    </div>
  );

  // ── Context side panel (re-skin of aa9746e's aside) ──
  const SidePanel = (
    <aside className="grid gap-5">
      {/* Stage track */}
      <div className="panel p-5">
        <p className="overline mb-4">{t("intake.stagesTitle")}</p>
        <div className="grid gap-2.5">
          {STAGE_ORDER.map((stage) => {
            const reached =
              !!stateQuery.data?.frontier_stage &&
              STAGE_ORDER.indexOf(stage) <= STAGE_ORDER.indexOf(stateQuery.data.frontier_stage as (typeof STAGE_ORDER)[number]);
            return (
              <div key={stage} className="flex items-center gap-3">
                <span className={`h-2 w-2 shrink-0 rounded-full ${reached ? "bg-evidence-400" : "bg-navy-100"}`} />
                <span className={`text-sm ${reached ? "text-ink-700" : "text-ink-400"}`}>{label("stage", stage)}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Saved answers (adaptive transcript) */}
      <div className="panel p-5">
        <p className="overline mb-4">{t("intake.savedAnswers")}</p>
        <div className="grid max-h-56 gap-2 overflow-y-auto">
          {transcript.map((turn, i) => (
            <div key={i} className="flex items-start gap-2.5 rounded-lg bg-navy-50 px-3 py-2.5">
              <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-evidence-50">
                <Check size={11} className="text-evidence-700" />
              </span>
              <span className="truncate text-xs text-ink-500">{turn.question || turn.answer}</span>
            </div>
          ))}
          {transcript.length === 0 && <p className="text-xs leading-relaxed text-ink-400">{t("intake.savedEmpty")}</p>}
        </div>

        {/* Progress-to-next meter (frontier-relative) */}
        {stateQuery.data && (
          <div className="mt-4 border-t border-navy-100 pt-4">
            <p className="mb-2 text-xs text-ink-400">{t("intake.confidenceEstimate")}</p>
            <div className="flex items-center gap-2">
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-navy-100">
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${Math.round(stateQuery.data.percent_to_next)}%`,
                    background: "linear-gradient(90deg, #0E8C74, #3DAE93)"
                  }}
                />
              </div>
              <span className="text-xs font-medium tabular-nums text-evidence-700">
                {Math.round(stateQuery.data.percent_to_next)}%
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Why answers matter */}
      <div className="panel p-5">
        <div className="mb-2 flex items-center gap-2">
          <ShieldCheck size={15} className="text-evidence-600" />
          <span className="text-sm font-semibold text-ink-900">{t("intake.everyAnswerTitle")}</span>
        </div>
        <p className="text-xs leading-relaxed text-ink-500">{t("intake.everyAnswerBody")}</p>
      </div>
    </aside>
  );

  return (
    <section className="grid gap-5" dir={dir}>
      {/* Success flash overlay (aa9746e) */}
      {showSuccess && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center pointer-events-none"
          style={{ background: "rgba(14, 140, 116, 0.12)" }}
        >
          <div className="grid h-20 w-20 place-items-center rounded-2xl shadow-trust-lg bg-evidence-600">
            <Check size={36} className="text-white" />
          </div>
        </div>
      )}

      {ProgressHeader}

      {/* ── Phase 1: industry selection ── */}
      {phase === "industry" && (
        <div className="panel max-w-2xl p-6 sm:p-8">
          <div className="mb-5 flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-lg bg-flag-600 text-white">
              <Sparkles size={20} />
            </div>
            <div>
              <h2 className="text-2xl font-semibold text-ink-900">{t("intake.flowIndustryTitle")}</h2>
              <p className="text-sm text-ink-500">{t("intake.flowIndustrySubtitle")}</p>
            </div>
          </div>
          {industriesQuery.isLoading ? (
            <LoadingState />
          ) : industriesQuery.isError ? (
            <div className="grid gap-3">
              <p className="text-sm text-flag-700">{String(industriesQuery.error)}</p>
              <button type="button" className="btn btn-secondary w-fit" onClick={() => industriesQuery.refetch()}>
                {t("common.retry")}
              </button>
            </div>
          ) : (
            <label className="mb-5 grid max-w-sm gap-1 text-sm font-medium text-ink-700">
              {t("intake.flowIndustryLabel")}
              <select className="input" value={industryKey} onChange={(e) => setIndustryKey(e.target.value)}>
                <option value="" disabled>
                  {t("intake.flowIndustryPlaceholder")}
                </option>
                {(industriesQuery.data ?? []).map((ind) => (
                  <option key={ind.key} value={ind.key}>
                    {ind.name}
                  </option>
                ))}
              </select>
            </label>
          )}
          <button
            className="btn btn-primary px-6 py-3"
            disabled={!industryKey || startClassify.isPending}
            onClick={() => startClassify.mutate()}
          >
            {startClassify.isPending ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
            {t("intake.flowStart")}
          </button>
          {startClassify.isError && <p className="mt-3 text-sm text-flag-700">{String(startClassify.error)}</p>}
        </div>
      )}

      {/* ── Phase 2: classification Q&A ── */}
      {phase === "classify" && step && (
        <div className="grid items-start gap-5 lg:grid-cols-[2fr_1fr]">
          <div className="panel flex min-h-[calc(100vh-20rem)] flex-col p-6 sm:p-8">
            <div className="my-auto w-full">
              <p className="overline mb-3">{t("intake.flowStepClassify")}</p>
              <h2
                className="mb-3 text-2xl font-semibold leading-snug text-ink-900 sm:text-3xl"
                style={{ letterSpacing: "-0.01em" }}
              >
                {step.question}
              </h2>
              {step.explanation && <p className="mb-8 text-sm leading-relaxed text-ink-400">{step.explanation}</p>}

              {step.options && step.options.length > 0 ? (
                <div className="mb-8 flex flex-col gap-2">
                  {step.options.map((opt) => (
                    <button
                      key={opt.index}
                      type="button"
                      disabled={answerClassify.isPending}
                      onClick={() => answerClassify.mutate({ index: opt.index, answerText: opt.text })}
                      className="flex items-center gap-4 rounded-xl border-2 px-5 py-4 text-start text-sm font-medium text-ink-800 transition-all duration-150 hover:border-navy-400 disabled:opacity-60"
                      style={{ borderColor: "#C7D3E8", background: "white" }}
                    >
                      {opt.text}
                    </button>
                  ))}
                </div>
              ) : (
                <form
                  className="grid gap-3"
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (classifyInput.trim())
                      answerClassify.mutate({ text: classifyInput.trim(), answerText: classifyInput.trim() });
                  }}
                >
                  <textarea
                    className="min-h-[110px] w-full rounded-xl border border-navy-200 px-5 py-4 text-lg text-ink-900 outline-none transition focus:border-navy-500 focus:ring-2 focus:ring-navy-100"
                    placeholder={t("intake.flowClassifyTextPlaceholder")}
                    value={classifyInput}
                    onChange={(e) => setClassifyInput(e.target.value)}
                    autoFocus
                  />
                  <button className="btn btn-primary w-fit px-6 py-3" disabled={answerClassify.isPending || !classifyInput.trim()}>
                    {answerClassify.isPending ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
                    {t("intake.flowContinue")}
                  </button>
                </form>
              )}
              {answerClassify.isError && <p className="mt-3 text-sm text-flag-700">{String(answerClassify.error)}</p>}
            </div>
          </div>
          {SidePanel}
        </div>
      )}

      {/* ── Transition: linking PML → intake ── */}
      {phase === "linking" && (
        <div className="panel max-w-2xl p-10 text-center">
          {link.isError ? (
            <p className="text-sm text-flag-700">{String(link.error)}</p>
          ) : (
            <div className="grid place-items-center gap-3">
              <Loader2 size={28} className="animate-spin text-navy-600" />
              <p className="text-sm text-ink-600">{t("intake.flowLinking", { stage: step?.phase ?? "—" })}</p>
            </div>
          )}
        </div>
      )}

      {/* ── Phase 3: adaptive intake / diagnosis ── */}
      {phase === "intake" && (
        <div className="grid items-start gap-5 lg:grid-cols-[2fr_1fr]">
          <div className="panel flex min-h-[calc(100vh-20rem)] flex-col p-6 sm:p-8">
            <div className="my-auto w-full">
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <p className="overline">
                  {t("intake.flowStepIntake")}
                  {stateQuery.data?.phase ? ` · ${t("intake.flowPhaseLabel")}: ${stateQuery.data.phase}` : ""}
                </p>
                <span className="chip bg-evidence-50 text-evidence-700 border border-evidence-100">
                  <ShieldCheck size={13} /> {t("intake.flowVerified")}
                </span>
              </div>

              {firedProbes.length > 0 && (
                <div className="mb-3 rounded-md border border-caution-100 bg-caution-50 px-3 py-2 text-sm text-caution-700">
                  <span className="font-medium">{t("intake.flowProbes")} :</span> {firedProbes.join(", ")}
                </div>
              )}
              {contradictions.length > 0 && (
                <div className="mb-3 grid gap-1 rounded-md border border-flag-200 bg-flag-50 px-3 py-2 text-sm text-flag-700">
                  {contradictions.map((item) => (
                    <div key={item.rule_id} className="flex items-start gap-2">
                      <AlertTriangle size={16} className="mt-0.5 shrink-0" />
                      <span>
                        <span className="font-medium">{item.field} :</span> {item.reason}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {ready || !question ? (
                <div className="grid gap-3">
                  <div className="flex items-center gap-2 text-evidence-700">
                    <Check size={18} /> {t("intake.flowDiagnosisReady")}
                  </div>
                  {diagnosisQuery.isLoading && <p className="text-sm text-ink-500">{t("intake.flowDiagnosisComputing")}</p>}
                  {diagnosisQuery.isError && <p className="text-sm text-flag-700">{String(diagnosisQuery.error)}</p>}
                  {diagnosisQuery.data && (
                    <div className="grid gap-3 rounded-md border border-evidence-100 bg-evidence-50 px-4 py-3">
                      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 text-sm text-ink-600">
                        <span>
                          {t("intake.flowDiagnosedStage")} :{" "}
                          <span className="font-semibold text-ink-900">
                            {label("stage", diagnosisQuery.data.diagnosis.diagnosed_stage)}
                          </span>
                        </span>
                        <span>
                          {t("intake.flowPerceivedStage")} :{" "}
                          <span className="font-medium">{label("stage", diagnosisQuery.data.diagnosis.declared_stage)}</span>
                        </span>
                        <span>
                          {t("intake.flowGap")} :{" "}
                          <span className="font-medium">{diagnosisQuery.data.diagnosis.gap_level}</span>
                        </span>
                      </div>
                      <Link to={`/projects/${projectId}/dashboard`} className="btn btn-primary w-fit px-6 py-3">
                        {t("intake.flowViewDashboard")}
                      </Link>
                    </div>
                  )}
                </div>
              ) : (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (answer.trim()) submit.mutate();
                  }}
                >
                  <h2
                    className="mb-3 text-2xl font-semibold leading-snug text-ink-900 sm:text-3xl"
                    style={{ letterSpacing: "-0.01em" }}
                  >
                    {question.text[language] ?? question.text.fr}
                  </h2>
                  <p className="mb-8 text-sm leading-relaxed text-ink-400">{t("intake.answerHint")}</p>

                  {question.options && question.options.length > 0 ? (
                    <div className="mb-8 flex flex-col gap-2">
                      {question.options.map((opt) => (
                        <button
                          key={opt}
                          type="button"
                          onClick={() => setAnswer(opt)}
                          className="flex items-center gap-4 rounded-xl border-2 px-5 py-4 text-start transition-all duration-150"
                          style={{
                            borderColor: answer === opt ? "#2E4D80" : "#C7D3E8",
                            background: answer === opt ? "#EEF2F9" : "white",
                            color: answer === opt ? "#13294B" : "#0F1B2D"
                          }}
                        >
                          <div
                            className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full border-2"
                            style={{ borderColor: answer === opt ? "#2E4D80" : "#C7D3E8" }}
                          >
                            {answer === opt && <div className="h-2 w-2 rounded-full" style={{ background: "#2E4D80" }} />}
                          </div>
                          <span className="text-sm font-medium">{opt}</span>
                        </button>
                      ))}
                    </div>
                  ) : (
                    <div className="mb-8">
                      <textarea
                        className="min-h-[90px] w-full rounded-xl border border-navy-200 bg-white px-5 py-4 text-lg text-ink-900 outline-none transition focus:border-navy-500 focus:ring-2 focus:ring-navy-100"
                        placeholder={language === "ar" ? "اكتب إجابتك هنا…" : t("intake.answerPlaceholder")}
                        value={answer}
                        onChange={(e) => setAnswer(e.target.value)}
                        autoFocus
                      />
                    </div>
                  )}

                  <div className="flex items-center justify-end">
                    <button type="submit" disabled={submit.isPending || !answer.trim()} className="btn btn-primary px-6 py-3">
                      {submit.isPending ? t("intake.saving") : t("intake.answer")}
                      <Send size={15} />
                    </button>
                  </div>
                  {submit.isError && <p className="mt-3 text-sm text-flag-700">{String(submit.error)}</p>}
                </form>
              )}
            </div>
          </div>
          {SidePanel}
        </div>
      )}
    </section>
  );
}

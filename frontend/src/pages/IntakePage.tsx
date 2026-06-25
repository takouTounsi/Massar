import { useMutation, useQuery } from "@tanstack/react-query";
import { AlertCircle, Check, ChevronLeft, FileText, Loader2, Send, ShieldCheck, Upload } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import type { ChangeEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { answerIntake, listIntakeEvidence, startIntake, uploadIntakeEvidence } from "../api/projects";
import { LoadingState } from "../components/LoadingState";
import { STAGE_ORDER } from "../lib/diagnosis";
import type { MessageKey } from "../i18n/locales";
import { useI18n } from "../i18n/useI18n";

const MAX_EVIDENCE_BYTES = 10 * 1024 * 1024;

function isPdfFile(file: File) {
  return file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
}

// Dimension chips reuse the app's semantic palette (evidence / navy / gold /
// caution) rather than a separate colour system. Labels resolve via i18n.
const DIMENSION_COLORS: Record<string, { bg: string; text: string; border: string; labelKey: MessageKey }> = {
  market_validation: { bg: "#E6F4F0", text: "#0A6E5B", border: "#CCE9E2", labelKey: "intake.dimMarket" },
  profile: { bg: "#EEF2F9", text: "#13294B", border: "#C7D3E8", labelKey: "intake.dimProfile" },
  maturity: { bg: "#FBF4E0", text: "#A87A12", border: "#F6E7BC", labelKey: "intake.dimMaturity" },
  goal: { bg: "#FBF1DE", text: "#8F5E18", border: "#F6E2BC", labelKey: "intake.dimGoal" },
  scalability: { bg: "#EEF2F9", text: "#2E4D80", border: "#C7D3E8", labelKey: "intake.dimScalability" },
  traction: { bg: "#FBF1DE", text: "#B7791F", border: "#F6E2BC", labelKey: "intake.dimTraction" },
  default: { bg: "#EEF2F9", text: "#5A6577", border: "#E7EDF6", labelKey: "intake.dimDefault" },
};

export function IntakePage() {
  const { projectId = "" } = useParams();
  const { t, label, language } = useI18n();
  const [value, setValue] = useState<string>("true");
  const [showSuccess, setShowSuccess] = useState(false);

  const sessionQuery = useQuery({
    queryKey: ["intake", projectId],
    queryFn: () => startIntake(projectId),
    enabled: Boolean(projectId),
  });

  const mutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) => answerIntake(projectId, payload),
    onSuccess: (data) => {
      setShowSuccess(true);
      setTimeout(() => setShowSuccess(false), 800);
      sessionQuery.refetch();
      setValue(data.session.next_question?.type === "boolean" ? "true" : "");
    },
  });

  const question = useMemo(
    () => mutation.data?.session.next_question ?? sessionQuery.data?.next_question ?? null,
    [mutation.data, sessionQuery.data]
  );
  const completed = mutation.data?.session.completed ?? sessionQuery.data?.completed ?? false;
  const askedCodes = sessionQuery.data?.asked_question_codes ?? [];
  const askedCount = askedCodes.length;
  const progressPct = Math.min(100, (askedCount / 20) * 100);
  const confidencePct = Math.min(100, (askedCount / 10) * 100);
  const sessionId = sessionQuery.data?.session_id;

  const dim = question?.tags?.[0] ?? "default";
  const dimConfig = DIMENSION_COLORS[dim] ?? DIMENSION_COLORS.default;

  // ── Evidence upload (PDF → backend → stored & linked to the session) ──
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);

  const evidenceQuery = useQuery({
    queryKey: ["intake-evidence", projectId, sessionId ?? null],
    queryFn: () => listIntakeEvidence(projectId, sessionId),
    enabled: Boolean(projectId),
  });

  const uploadMutation = useMutation({
    mutationFn: (file: File) =>
      uploadIntakeEvidence(projectId, file, { sessionId, questionCode: question?.code }, setUploadProgress),
    onMutate: () => {
      setUploadError(null);
      setUploadProgress(0);
    },
    onSuccess: () => {
      setUploadProgress(null);
      evidenceQuery.refetch();
    },
    onError: (err) => {
      setUploadProgress(null);
      setUploadError(err instanceof Error ? err.message : t("intake.evidenceFailed"));
    },
  });

  const handleFileSelected = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = ""; // allow re-selecting the same file
    if (!file) return;
    setUploadError(null);
    if (!isPdfFile(file)) {
      setUploadError(t("intake.evidenceInvalid"));
      return;
    }
    if (file.size > MAX_EVIDENCE_BYTES) {
      setUploadError(t("intake.evidenceTooLarge"));
      return;
    }
    uploadMutation.mutate(file);
  };

  const attachments = evidenceQuery.data ?? [];

  if (sessionQuery.isLoading) return <LoadingState />;

  // ── Completed state ──
  if (completed || !question) {
    return (
      <section className="grid min-h-[calc(100vh-12rem)] place-items-center">
        <div className="panel max-w-md p-10 text-center">
          <div className="mx-auto mb-6 grid h-20 w-20 place-items-center rounded-2xl bg-evidence-600">
            <Check size={36} className="text-white" />
          </div>
          <h2 className="text-2xl font-semibold text-ink-900 mb-2">{t("intake.completedTitle")}</h2>
          <p className="text-ink-500 mb-8">{t("intake.completedBody")}</p>
          <Link to={`/projects/${projectId}/dashboard`} className="btn btn-primary px-6 py-3">
            {t("intake.runAnalysis")}
          </Link>
        </div>
      </section>
    );
  }

  return (
    <section className="grid gap-5">
      {/* Success flash overlay */}
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

      {/* ── Progress header ── */}
      <div className="panel p-4">
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <span className="text-sm font-medium text-ink-700">{t("intake.questionN", { n: askedCount + 1 })}</span>
          <span className="text-navy-200">·</span>
          <span
            className="inline-flex items-center rounded-lg px-3 py-1 text-xs font-semibold"
            style={{ background: dimConfig.bg, color: dimConfig.text, border: `1px solid ${dimConfig.border}` }}
          >
            {t(dimConfig.labelKey)}
          </span>
          {question.tags?.includes("fundamental") && (
            <span className="chip bg-caution-50 text-caution-700 border border-caution-100">
              {t("intake.fundamental")}
            </span>
          )}
          <span className="ms-auto text-xs font-medium tabular-nums text-ink-400">{Math.round(progressPct)}%</span>
        </div>
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-navy-100">
          <div className="h-full rounded-full bg-evidence-600 transition-all duration-700" style={{ width: `${progressPct}%` }} />
        </div>
      </div>

      {/* ── Main: question (primary) + context side panel ── */}
      <div className="grid items-start gap-5 lg:grid-cols-[2fr_1fr]">
        {/* Question + answer */}
        <div className="panel flex min-h-[calc(100vh-20rem)] flex-col p-6 sm:p-8">
          <div className="my-auto w-full">
            <h2 className="mb-3 text-2xl font-semibold leading-snug text-ink-900 sm:text-3xl" style={{ letterSpacing: "-0.01em" }}>
              {question.text[language] ?? question.text.fr}
            </h2>
            <p className="mb-8 text-sm leading-relaxed text-ink-400">{t("intake.answerHint")}</p>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                const typedValue =
                  question.type === "integer"
                    ? Number.parseInt(value, 10)
                    : question.type === "number"
                    ? Number.parseFloat(value)
                    : question.type === "boolean"
                    ? value === "true"
                    : value;
                mutation.mutate({
                  session_id: sessionQuery.data?.session_id,
                  question_code: question.code,
                  value: typedValue,
                });
              }}
            >
              {/* Boolean: two large tiles */}
              {question.type === "boolean" || question.options?.length === 0 ? (
                <div className="mb-8 flex flex-col gap-4 sm:flex-row">
                  {[
                    { val: "true", label: t("intake.yes") },
                    { val: "false", label: t("intake.no") },
                  ].map(({ val, label }) => (
                    <button
                      key={val}
                      type="button"
                      onClick={() => setValue(val)}
                      className="flex-1 rounded-2xl border-2 py-6 text-lg font-medium transition-all duration-150"
                      style={{
                        borderColor: value === val ? "#2E4D80" : "#C7D3E8",
                        background: value === val ? "#EEF2F9" : "white",
                        color: value === val ? "#13294B" : "#5A6577",
                        transform: value === val ? "scale(1.02)" : "scale(1)",
                      }}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              ) : question.options && question.options.length > 0 ? (
                /* Single choice: vertical option list */
                <div className="mb-8 flex flex-col gap-2">
                  {question.options.map((opt) => (
                    <button
                      key={opt}
                      type="button"
                      onClick={() => setValue(opt)}
                      className="flex items-center gap-4 rounded-xl border-2 px-5 py-4 text-start transition-all duration-150"
                      style={{
                        borderColor: value === opt ? "#2E4D80" : "#C7D3E8",
                        background: value === opt ? "#EEF2F9" : "white",
                        color: value === opt ? "#13294B" : "#0F1B2D",
                      }}
                    >
                      <div
                        className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full border-2"
                        style={{ borderColor: value === opt ? "#2E4D80" : "#C7D3E8" }}
                      >
                        {value === opt && <div className="h-2 w-2 rounded-full" style={{ background: "#2E4D80" }} />}
                      </div>
                      <span className="text-sm font-medium">{opt}</span>
                    </button>
                  ))}
                </div>
              ) : (
                /* Text / number input */
                <div className="mb-8">
                  <input
                    className="w-full rounded-xl border border-navy-200 bg-white px-5 py-4 text-lg text-ink-900 outline-none transition focus:border-navy-500 focus:ring-2 focus:ring-navy-100"
                    value={value}
                    onChange={(e) => setValue(e.target.value)}
                    type={question.type === "integer" || question.type === "number" ? "number" : "text"}
                    placeholder={question.type === "integer" ? "0" : t("intake.answerPlaceholder")}
                    autoFocus
                  />
                </div>
              )}

              {/* Evidence upload — PDF picker → multipart upload → stored on the
                  backend and linked to this session. No fabricated success. */}
              <div className="mb-8">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="application/pdf,.pdf"
                  className="hidden"
                  onChange={handleFileSelected}
                />
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploadMutation.isPending}
                  className="w-full rounded-xl border-2 border-dashed border-navy-200 text-start transition hover:border-navy-400 disabled:cursor-wait"
                >
                  <div className="flex items-center gap-4 px-5 py-4">
                    <div className="grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-navy-200 bg-white">
                      {uploadMutation.isPending ? (
                        <Loader2 size={15} className="animate-spin text-navy-600" />
                      ) : (
                        <Upload size={15} className="text-ink-400" />
                      )}
                    </div>
                    <div>
                      <p className="text-sm font-medium text-ink-700">
                        {uploadMutation.isPending ? t("intake.evidenceUploading") : t("intake.evidenceTitle")}
                      </p>
                      <p className="text-xs text-ink-400">{t("intake.evidenceHint")}</p>
                    </div>
                  </div>
                  {uploadProgress !== null && (
                    <div className="mx-5 mb-3 h-1 overflow-hidden rounded-full bg-navy-100">
                      <div className="h-full rounded-full bg-evidence-600 transition-all" style={{ width: `${uploadProgress}%` }} />
                    </div>
                  )}
                </button>

                {uploadError && (
                  <p className="mt-2 flex items-center gap-1.5 text-xs text-flag-700">
                    <AlertCircle size={13} /> {uploadError}
                  </p>
                )}

                {/* Attachments tied to this session */}
                {attachments.length > 0 && (
                  <ul className="mt-3 grid gap-2">
                    {attachments.map((att) => (
                      <li key={att.evidence_id} className="flex items-center gap-2.5 rounded-lg border border-evidence-100 bg-evidence-50 px-3 py-2">
                        <FileText size={14} className="shrink-0 text-evidence-700" />
                        <span className="truncate text-xs font-medium text-evidence-700">{att.filename}</span>
                        <span className="ms-auto shrink-0 text-[10px] tabular-nums text-ink-400">
                          {(att.size / 1024).toFixed(0)} KB
                        </span>
                        <Check size={13} className="shrink-0 text-evidence-600" />
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              {/* Submit */}
              <div className="flex items-center justify-between">
                <button
                  type="button"
                  className="flex items-center gap-2 text-sm text-ink-400 hover:text-ink-500"
                  onClick={() => sessionQuery.refetch()}
                >
                  <ChevronLeft size={15} /> {t("intake.previous")}
                </button>
                <button type="submit" disabled={mutation.isPending} className="btn btn-primary px-6 py-3">
                  {mutation.isPending ? t("intake.saving") : t("intake.answer")}
                  <Send size={15} />
                </button>
              </div>
            </form>
          </div>
        </div>

        {/* Context side panel */}
        <aside className="grid gap-5">
          {/* Stage track */}
          <div className="panel p-5">
            <p className="overline mb-4">{t("intake.stagesTitle")}</p>
            <div className="grid gap-2.5">
              {STAGE_ORDER.map((stage, i) => (
                <div key={stage} className="flex items-center gap-3">
                  <span className={`h-2 w-2 shrink-0 rounded-full ${i < 2 ? "bg-evidence-400" : "bg-navy-100"}`} />
                  <span className={`text-sm ${i < 2 ? "text-ink-700" : "text-ink-400"}`}>{label("stage", stage)}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Answered responses */}
          <div className="panel p-5">
            <p className="overline mb-4">{t("intake.savedAnswers")}</p>
            <div className="grid max-h-56 gap-2 overflow-y-auto">
              {askedCodes.map((code) => (
                <div key={code} className="flex items-center gap-2.5 rounded-lg bg-navy-50 px-3 py-2.5">
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-evidence-50">
                    <Check size={11} className="text-evidence-700" />
                  </span>
                  <span className="truncate text-xs text-ink-500">{code}</span>
                </div>
              ))}
              {askedCount === 0 && <p className="text-xs leading-relaxed text-ink-400">{t("intake.savedEmpty")}</p>}
            </div>

            {/* Confidence meter */}
            <div className="mt-4 border-t border-navy-100 pt-4">
              <p className="mb-2 text-xs text-ink-400">{t("intake.confidenceEstimate")}</p>
              <div className="flex items-center gap-2">
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-navy-100">
                  <div
                    className="h-full rounded-full"
                    style={{ width: `${confidencePct}%`, background: "linear-gradient(90deg, #0E8C74, #3DAE93)" }}
                  />
                </div>
                <span className="text-xs font-medium tabular-nums text-evidence-700">{confidencePct.toFixed(0)}%</span>
              </div>
            </div>
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
      </div>
    </section>
  );
}

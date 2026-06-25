import { BrainCircuit, Check, FileUp, Info, Loader2, ShieldCheck, TrendingUp, Workflow } from "lucide-react";
import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { motion } from "framer-motion";
import { ArchetypeHero } from "../components/ArchetypeHero";
import { BoardSummaryGrid } from "../components/Boardsummarygrid";
import { BottleneckAccordion } from "../components/BottleneckAccordion";
import { ConfidenceRing } from "../components/ConfidenceRing";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingState } from "../components/LoadingState";
import { NoDiagnosisState } from "../components/NoDiagnosisState";
import { SWOTGrid } from "../components/Swotgrid";
import { useProjectDashboard } from "../hooks/useProjectDashboard";
import { deriveReadiness, rankActionLeverage } from "../lib/intelligence";
import { sectionVariants } from "../lib/anim";
import { usePrefersReducedMotion } from "../lib/motion";
import { useI18n } from "../i18n/useI18n";

type QuestState = "idle" | "uploading" | "verified";

export function IntelligencePage() {
  const { projectId = "" } = useParams();
  const dashboardQuery = useProjectDashboard(projectId);
  const reduced = usePrefersReducedMotion();
  const { t, label, text } = useI18n();
  const [states, setStates] = useState<Record<string, QuestState>>({});

  const missing = useMemo(() => dashboardQuery.data?.analysis?.missing_fields ?? [], [dashboardQuery.data]);
  const base = dashboardQuery.data?.analysis?.maturity_confidence ?? 0;

  if (dashboardQuery.isLoading) return <LoadingState />;
  if (dashboardQuery.isError) return <ErrorState message={t("dashboard.loadError")} onRetry={() => dashboardQuery.refetch()} />;
  if (!dashboardQuery.data) return <EmptyState title={t("dashboard.projectNotFound")} />;
  if (!dashboardQuery.data.analysis) return <NoDiagnosisState projectId={projectId} />;

  const analysis = dashboardQuery.data.analysis;
  const readiness = deriveReadiness(analysis);
  const leverage = rankActionLeverage(analysis, analysis.roadmap?.actions ?? []).slice(0, 6);
  const maxLev = leverage.length > 0 ? Math.max(...leverage.map((l) => l.leverage), 1) : 1;

  // Archetype / SWOT / board-summary narrative fields are produced by the
  // intelligence service's LLM-assisted seams (see scoring_intelligence.py).
  // DemoDashboard does not yet carry them, so they render as honest empty
  // states below rather than being fabricated client-side. Once the API
  // returns an IntelligenceReport, thread `report.archetype` / `report.swot`
  // / `report.board_summary` in here directly.
  const archetype = null;
  const swot = null;
  const boardSummary = null;

  const verifiedCount = Object.values(states).filter((s) => s === "verified").length;
  const perQuest = missing.length > 0 ? Math.max(3, Math.round(((0.96 - base) * 100) / missing.length)) : 0;
  const projected = Math.min(99, Math.round(base * 100) + verifiedCount * perQuest);
  const allClear = missing.length > 0 && verifiedCount === missing.length;

  const startQuest = (field: string) => {
    setStates((cur) => ({ ...cur, [field]: "uploading" }));
    const finish = () => setStates((cur) => ({ ...cur, [field]: "verified" }));
    if (reduced) finish();
    else window.setTimeout(finish, 1300);
  };

  return (
    <motion.section initial="hidden" animate="visible" variants={{ visible: { transition: { staggerChildren: 0.06 } } }} className="grid gap-5">
      <motion.div custom={0} variants={sectionVariants}>
        <h2 className="flex items-center gap-2 text-2xl font-semibold text-ink-900">
          <BrainCircuit size={22} className="text-navy-700" /> {t("intel.title")}
        </h2>
        <p className="text-sm text-ink-500">{t("intel.subtitle")}</p>
      </motion.div>

      {/* Section A — readiness ring + bottleneck chain */}
      <motion.div custom={1} variants={sectionVariants} className="panel grid gap-5 p-5 md:grid-cols-[auto_1fr]">
        <div className="flex items-center gap-5">
          <ConfidenceRing value={readiness.overall} tone="navy" caption={t("intel.readinessCaption")} decimals={1} />
          <div className="grid gap-2">
            <div>
              <p className="text-overline text-ink-400">{t("intel.withoutPenalty")}</p>
              <p className="text-sm font-semibold tabular-nums text-ink-500">{readiness.withoutPenalty}</p>
            </div>
            <div>
              <p className="text-overline text-ink-400">{t("intel.bottleneckCost")}</p>
              <p className="text-sm font-semibold tabular-nums text-flag-700">{readiness.bottleneckCost}</p>
            </div>
            <div>
              <p className="text-overline text-ink-400">{t("intel.weakestFloor")}</p>
              <p className="text-sm font-semibold tabular-nums text-flag-700">{readiness.weakestFloor}</p>
            </div>
          </div>
        </div>
        <div>
          <p className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-ink-900">
            <Workflow size={16} className="text-navy-700" /> {t("intel.bottleneckTitle")}
          </p>
          <BottleneckAccordion analysis={analysis} projectId={projectId} />
        </div>
      </motion.div>

      {/* Section C — founder archetype (cinematic hero, real-data-or-honest-empty) */}
      <motion.div custom={2} variants={sectionVariants}>
        <ArchetypeHero data={archetype} />
      </motion.div>

      {/* Section B — counterfactual action leverage */}
      {leverage.length > 0 ? (
        <motion.div custom={3} variants={sectionVariants} className="panel p-5">
          <p className="flex items-center gap-1.5 font-semibold text-ink-900">
            <TrendingUp size={16} className="text-evidence-600" /> {t("intel.leverageTitle")}
          </p>
          <p className="mt-0.5 text-xs text-ink-400">{t("intel.leverageNote")}</p>
          <div className="mt-4 grid gap-2.5">
            {leverage.map((row) => {
              const levTone = row.leverage > 5 ? "bg-evidence-50 text-evidence-700" : row.leverage >= 1 ? "bg-caution-50 text-caution-700" : "bg-navy-50 text-ink-500";
              return (
                <div key={row.action.id} className="grid grid-cols-[1fr_auto] items-center gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm text-ink-700">{text(row.action.title)}</p>
                    <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-navy-100">
                      <div className="h-full rounded-full bg-evidence-500 transition-[width] duration-700 ease-sovereign" style={{ width: `${Math.round((row.leverage / maxLev) * 100)}%` }} />
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-2 text-xs">
                    <span className="font-semibold tabular-nums text-evidence-700">+{row.gain}</span>
                    <span className="tabular-nums text-ink-400">{row.effort} {t("intel.weeks")}</span>
                    <span className={`chip ${levTone}`}>{t("intel.leverageBadge", { value: row.leverage })}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </motion.div>
      ) : null}

      {/* Section D + F — SWOT and board summary side by side on wide screens */}
      <motion.div custom={4} variants={sectionVariants} className="grid gap-5 lg:grid-cols-2">
        <SWOTGrid data={swot} />
        <BoardSummaryGrid data={boardSummary} />
      </motion.div>

      {/* Confidence recovery meter — climbs as evidence is verified */}
      <motion.div custom={5} variants={sectionVariants} className="hero-cinematic p-6">
        <div className="relative flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-overline text-navy-200">{t("intel.confidenceNow")}</p>
            <p className="mt-1 text-4xl font-bold tabular-nums text-white">
              {projected}
              <span className="text-xl">%</span>
            </p>
          </div>
          <ShieldCheck size={28} className="text-evidence-400" />
        </div>
        <div className="relative mt-4 h-2.5 overflow-hidden rounded-full bg-white/15">
          <div
            className="h-full rounded-full bg-gradient-to-r from-evidence-600 to-evidence-400 transition-[width] duration-500 ease-sovereign"
            style={{ width: `${projected}%` }}
          />
        </div>
      </motion.div>

      {/* Quests */}
      <motion.div custom={6} variants={sectionVariants} className="panel p-5">
        <h3 className="font-semibold text-ink-900">{t("intel.questTitle")}</h3>
        {allClear ? (
          <p className="mt-3 inline-flex items-center gap-2 rounded-lg bg-evidence-50 px-3 py-2 text-sm font-semibold text-evidence-700">
            <Check size={16} /> {t("intel.allClear")}
          </p>
        ) : null}
        <div className="mt-4 grid gap-2.5">
          {missing.map((field) => {
            const state = states[field] ?? "idle";
            return (
              <div
                key={field}
                className={`relative overflow-hidden rounded-card border-2 p-4 transition duration-300 ${
                  state === "verified" ? "border-evidence-300 bg-evidence-50/50 shadow-glow-evidence" : "border-caution-200 bg-white"
                }`}
              >
                {state === "uploading" ? (
                  <span aria-hidden className="pointer-events-none absolute inset-x-0 top-0 h-16 animate-scan bg-gradient-to-b from-evidence-500/30 to-transparent" />
                ) : null}
                <div className="relative flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <span
                      className={`grid h-9 w-9 place-items-center rounded-lg ${
                        state === "verified" ? "bg-evidence-600 text-white" : "bg-caution-50 text-caution-600"
                      }`}
                    >
                      {state === "verified" ? <Check size={17} /> : state === "uploading" ? <Loader2 size={17} className="animate-spin" /> : <FileUp size={17} />}
                    </span>
                    <div>
                      <p className="text-sm font-semibold text-ink-900">{label("field", field)}</p>
                      <p className="text-xs text-ink-500">
                        {state === "verified" ? t("intel.verified") : state === "uploading" ? t("intel.uploading") : t("intel.gain", { points: perQuest })}
                      </p>
                    </div>
                  </div>
                  {state === "verified" ? (
                    <span className="chip bg-evidence-600 text-white">{t("intel.gain", { points: perQuest })}</span>
                  ) : (
                    <button className="btn btn-primary" disabled={state === "uploading"} onClick={() => startQuest(field)}>
                      <FileUp size={15} /> {t("intel.provideEvidence")}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
          {missing.length === 0 ? <EmptyState title={t("intel.allClear")} /> : null}
        </div>

        <p className="mt-4 flex items-start gap-1.5 border-t border-navy-100 pt-3 text-xs text-ink-400">
          <Info size={13} className="mt-0.5 shrink-0" />
          {t("intel.flagNote")}
        </p>
      </motion.div>
    </motion.section>
  );
}
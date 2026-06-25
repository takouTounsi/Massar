import { motion } from "framer-motion";
import { ChevronDown, Layers, Sigma } from "lucide-react";
import { useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { AnomalyMoments } from "../components/AnomalyMoment";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingState } from "../components/LoadingState";
import { NoDiagnosisState } from "../components/NoDiagnosisState";
import { ScoreCascade } from "../components/ScoreCascade";
import { useProjectDashboard } from "../hooks/useProjectDashboard";
import { sectionVariants } from "../lib/anim";
import { weakestScore } from "../lib/diagnosis";
import { useI18n } from "../i18n/useI18n";

/**
 * Compact stat used in the page header strip — composite, weakest link,
 * and dimension count. Mirrors the dashboard's command-stat language so the
 * two pages feel like the same instrument panel.
 */
function HeaderStat({ label, value, tone = "ink" }: { label: string; value: string; tone?: "ink" | "flag" | "evidence" }) {
  const toneClass = tone === "flag" ? "text-flag-700" : tone === "evidence" ? "text-evidence-700" : "text-ink-900";
  return (
    <div className="flex flex-col gap-0.5 border-s border-navy-100 ps-4 first:border-0 first:ps-0">
      <span className="text-overline text-ink-400">{label}</span>
      <span className={`text-lg font-medium tabular-nums ${toneClass}`}>{value}</span>
    </div>
  );
}

export function ScoresPage() {
  const { projectId = "" } = useParams();
  const [params] = useSearchParams();
  const dashboardQuery = useProjectDashboard(projectId);
  const { t, label } = useI18n();
  const [howOpen, setHowOpen] = useState(false);

  if (dashboardQuery.isLoading) return <LoadingState />;
  if (dashboardQuery.isError) return <ErrorState message={t("dashboard.loadError")} onRetry={() => dashboardQuery.refetch()} />;
  if (!dashboardQuery.data) return <EmptyState title={t("dashboard.projectNotFound")} />;
  if (!dashboardQuery.data.analysis) return <NoDiagnosisState projectId={projectId} />;

  const { analysis } = dashboardQuery.data;
  const initialDim = params.get("dim");
  const scores = analysis.scores;
  const values = Object.values(scores);
  const composite = values.length ? Math.round(values.reduce((s, v) => s + v, 0) / values.length) : 0;
  const weakest = weakestScore(scores);
  const weakestValue = weakest ? Math.round(scores[weakest]) : 0;

  return (
    <motion.section initial="hidden" animate="visible" variants={{ visible: { transition: { staggerChildren: 0.06 } } }} className="grid gap-5">
      <motion.div custom={0} variants={sectionVariants} className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="flex items-center gap-2 text-2xl font-semibold text-ink-900">
            <Layers size={22} className="text-navy-700" /> {t("scores.title")}
          </h2>
          <p className="mt-1 text-sm text-ink-500">{t("scores.subtitle")}</p>
        </div>
        <div className="flex items-center gap-4 rounded-card border border-navy-100 bg-white px-5 py-3 shadow-trust">
          <HeaderStat label={t("scores.composite")} value={`${composite}/100`} />
          <HeaderStat label={weakest ? label("score", weakest) : t("scores.weakestLink")} value={`${weakestValue}`} tone="flag" />
          <HeaderStat label="λ" value="0.5" />
        </div>
      </motion.div>

      <motion.div custom={1} variants={sectionVariants}>
        <ScoreCascade analysis={analysis} projectId={projectId} initialDim={initialDim} />
      </motion.div>

      <motion.div custom={2} variants={sectionVariants}>
        <AnomalyMoments analysis={analysis} projectId={projectId} />
      </motion.div>

      {/* "How this is calculated" — non-intrusive trust disclosure, kept exactly
          as before but with a clearer icon + slightly richer formula trace so
          it reads as a real engine, not a tooltip. */}
      <motion.div custom={3} variants={sectionVariants} className="rounded-card border border-navy-100 bg-white">
        <button
          type="button"
          onClick={() => setHowOpen((v) => !v)}
          aria-expanded={howOpen}
          className="flex w-full items-center justify-between gap-3 px-4 py-3 text-start text-sm font-medium text-ink-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-400"
        >
          <span className="flex items-center gap-2">
            <Sigma size={15} className="text-navy-600" /> {t("scores.howTitle")}
          </span>
          <ChevronDown size={16} className={`text-ink-400 transition-transform duration-300 ${howOpen ? "rotate-180" : ""}`} />
        </button>
        {howOpen ? (
          <div className="space-y-3 border-t border-navy-100 px-4 py-4 text-sm text-ink-600">
            <div className="grid gap-2 sm:grid-cols-3">
              <div className="rounded-lg border border-navy-100 bg-navy-50/40 p-3">
                <p className="text-overline text-navy-600">{t("scores.howStep1").split(":")[0]}</p>
                <p className="mt-1 text-xs leading-relaxed text-ink-600">{t("scores.howStep1")}</p>
              </div>
              <div className="rounded-lg border border-flag-100 bg-flag-50/40 p-3">
                <p className="text-overline text-flag-700">{t("scores.howStep2").split(":")[0]}</p>
                <p className="mt-1 text-xs leading-relaxed text-ink-600">{t("scores.howStep2")}</p>
              </div>
              <div className="rounded-lg border border-evidence-100 bg-evidence-50/40 p-3">
                <p className="text-overline text-evidence-700">{t("scores.howStep3").split(":")[0]}</p>
                <p className="mt-1 text-xs leading-relaxed text-ink-600">{t("scores.howStep3")}</p>
              </div>
            </div>
            <p className="pt-1 font-mono text-xs text-ink-400">{t("scores.version")}</p>
          </div>
        ) : null}
      </motion.div>
    </motion.section>
  );
}
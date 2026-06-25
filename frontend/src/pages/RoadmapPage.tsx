import { motion } from "framer-motion";
import { GitBranch, Map, RefreshCw, Route, Sparkles } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingState } from "../components/LoadingState";
import { RoadmapTree } from "../components/RoadmapTree";
import { useProjectDashboard } from "../hooks/useProjectDashboard";
import { useRoadmap } from "../hooks/useRoadmap";
import { sectionVariants } from "../lib/anim";
import { useI18n } from "../i18n/useI18n";

export function RoadmapPage() {
  const { projectId = "" } = useParams();
  const { roadmapQuery, generateMutation, regenerateMutation, updateActionMutation } = useRoadmap(projectId);
  const dashboardQuery = useProjectDashboard(projectId);
  const { t, label, text } = useI18n();

  if (roadmapQuery.isLoading) return <LoadingState />;
  if (roadmapQuery.isError) {
    return (
      <EmptyState
        title={t("roadmap.notGenerated")}
        action={
          <button className="btn btn-primary" onClick={() => generateMutation.mutate()} disabled={generateMutation.isPending}>
            <Sparkles size={16} /> {t("dashboard.generateRoadmap")}
          </button>
        }
      >
        {t("roadmap.notGeneratedHint")}
      </EmptyState>
    );
  }
  const roadmap = roadmapQuery.data;
  if (!roadmap) return <ErrorState message={t("roadmap.unavailable")} />;

  const scores = dashboardQuery.data?.analysis?.scores;
  const total = roadmap.actions.length;
  const done = roadmap.actions.filter((a) => a.status === "COMPLETED" || a.status === "DONE").length;
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;

  return (
    <motion.section initial="hidden" animate="visible" variants={{ visible: { transition: { staggerChildren: 0.06 } } }} className="grid gap-5">
      {/* Header strip — version, focus narrative, and the regenerate controls */}
      <motion.div custom={0} variants={sectionVariants} className="panel-navy flex flex-wrap items-center justify-between gap-4 p-5">
        <div className="min-w-0">
          <p className="inline-flex items-center gap-1.5 text-overline text-navy-200">
            <GitBranch size={12} /> {t("roadmap.tree")} · {roadmap.roadmap_version}
          </p>
          <h2 className="mt-1 truncate text-xl font-semibold text-white">{text(roadmap.summary.current_focus)}</h2>
          <p className="text-sm text-navy-200">
            {t("roadmap.nextTarget", { stage: label("stage", roadmap.summary.next_stage_target) })} ·{" "}
            {t("confidence.label", { percent: Math.round(roadmap.summary.confidence * 100) })}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <Link className="btn btn-secondary !border-white/20 !bg-white/10 !text-white hover:!bg-white/20" to={`/projects/${projectId}/journey`}>
            <Route size={16} /> {t("layout.journey")}
          </Link>
          <button
            className="btn btn-secondary !border-white/20 !bg-white/10 !text-white hover:!bg-white/20"
            onClick={() => regenerateMutation.mutate()}
            disabled={regenerateMutation.isPending}
          >
            <RefreshCw size={16} className={regenerateMutation.isPending ? "animate-spin" : ""} /> {t("roadmap.regenerate")}
          </button>
        </div>
      </motion.div>

      {/* Progress strip — a single readable number instead of leaving the page
          feeling like a bare list. Mirrors ProgressSummary's visual language. */}
      <motion.div custom={1} variants={sectionVariants} className="panel flex flex-wrap items-center gap-5 p-5">
        <div className="shrink-0">
          <p className="overline">{t("progress.global")}</p>
          <p className="mt-1 text-2xl font-semibold text-ink-900">{pct}%</p>
        </div>
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-navy-100">
          <motion.div
            className="h-full rounded-full bg-evidence-600"
            initial={{ width: 0 }}
            animate={{ width: `${Math.max(4, pct)}%` }}
            transition={{ duration: 0.7, ease: "easeOut" }}
          />
        </div>
        <span className="shrink-0 text-sm text-ink-500">
          {done}/{total} {t("common.completed").toLowerCase()}
        </span>
      </motion.div>

      <motion.div custom={2} variants={sectionVariants} className="panel p-5">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="font-semibold text-ink-900">{t("roadmap.tree")}</h3>
          <div className="flex flex-wrap items-center gap-3 text-xs text-ink-500">
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-evidence-600" /> {label("horizon", "IMMEDIATE")}
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-caution-600" /> {label("horizon", "SHORT_TERM")}
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-navy-500" /> {label("horizon", "MEDIUM_TERM")}
            </span>
          </div>
        </div>
        {roadmap.actions.length > 0 ? (
          <RoadmapTree
            actions={roadmap.actions}
            isUpdating={updateActionMutation.isPending}
            onStatusChange={(actionId, status) => updateActionMutation.mutate({ actionId, status })}
            scores={scores}
          />
        ) : (
          <EmptyState
            title={t("dashboard.noRoadmap")}
            action={
              <button className="btn btn-primary" onClick={() => generateMutation.mutate()}>
                <Map size={16} /> {t("dashboard.generateNow")}
              </button>
            }
          >
            {t("roadmap.notGeneratedHint")}
          </EmptyState>
        )}
      </motion.div>

      {roadmap.missing_information_actions.length > 0 ? (
        <motion.div custom={3} variants={sectionVariants} className="panel p-5">
          <h3 className="font-semibold text-ink-900">{t("roadmap.missingInfo")}</h3>
          <div className="mt-3 grid gap-2">
            {roadmap.missing_information_actions.map((item) => (
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-navy-100 p-3" key={item.field}>
                <div>
                  <p className="font-medium text-ink-900">{label("field", item.field)}</p>
                  <p className="text-sm text-ink-500">{text(item.reason)}</p>
                </div>
                <Link className="btn btn-secondary shrink-0" to={`/projects/${projectId}/intake`}>
                  {t("roadmap.completeInIntake")} →
                </Link>
              </div>
            ))}
          </div>
        </motion.div>
      ) : null}
    </motion.section>
  );
}
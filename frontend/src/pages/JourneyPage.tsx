import { Check, Circle, Flag, Info, MapPin } from "lucide-react";
import { useParams } from "react-router-dom";
import { ConfidenceRing } from "../components/ConfidenceRing";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingState } from "../components/LoadingState";
import { NoDiagnosisState } from "../components/NoDiagnosisState";
import { StageTrack } from "../components/GapGauge";
import { Timeline } from "../components/Timeline";
import type { TimelineItem } from "../components/Timeline";
import { useProjectDashboard } from "../hooks/useProjectDashboard";
import { STAGE_ORDER, gapTone, stageIndex } from "../lib/diagnosis";
import { useI18n } from "../i18n/useI18n";

export function JourneyPage() {
  const { projectId = "" } = useParams();
  const dashboardQuery = useProjectDashboard(projectId);
  const { t, label, text } = useI18n();

  if (dashboardQuery.isLoading) return <LoadingState />;
  if (dashboardQuery.isError) return <ErrorState message={t("dashboard.loadError")} onRetry={() => dashboardQuery.refetch()} />;
  if (!dashboardQuery.data) return <EmptyState title={t("journey.emptyEvents")} />;
  if (!dashboardQuery.data.analysis) return <NoDiagnosisState projectId={projectId} />;

  const { analysis } = dashboardQuery.data;
  const actions = analysis.roadmap?.actions ?? [];
  const completed = actions.filter((action) => action.status === "COMPLETED" || action.status === "DONE");
  const tone = gapTone(analysis.gap_level);
  const diagnosedIdx = Math.max(0, stageIndex(analysis.diagnosed_stage));
  const stagesReached = diagnosedIdx + 1;
  const ringPct = Math.round((stagesReached / STAGE_ORDER.length) * 100);
  const nextStage = STAGE_ORDER[Math.min(diagnosedIdx + 1, STAGE_ORDER.length - 1)];
  const gateItems = [
    ...analysis.blockers.filter((b) => b.stage_blocking).map((b) => ({ id: b.id, text: label("blocker", b.type), done: false })),
    ...analysis.missing_fields.map((f) => ({ id: f, text: label("field", f), done: false }))
  ];

  const items: TimelineItem[] = [
    {
      id: "declared",
      title: t("timeline.declaredStage"),
      subtitle: label("stage", analysis.declared_stage),
      tone: "navy",
      icon: <Flag size={9} />
    },
    {
      id: "diagnosed",
      title: t("timeline.diagnosedStage"),
      subtitle: `${label("stage", analysis.diagnosed_stage)} · ${t("gap.level", { gap: label("gap", analysis.gap_level) })}`,
      tone,
      icon: <MapPin size={9} />
    },
    ...completed.map((action) => ({
      id: action.id,
      title: text(action.title),
      subtitle: t("journey.completedWithEffort", { effort: action.estimated_effort }),
      tone: "evidence" as const,
      icon: <Check size={9} />
    })),
    { id: "now", title: t("timeline.now"), tone: "navy" as const, current: true }
  ];

  return (
    <section className="grid gap-4">
      <div>
        <h2 className="text-2xl font-semibold text-ink-900">{t("journey.title")}</h2>
        <p className="text-sm text-ink-500">{t("journey.summary", { completed: completed.length, total: actions.length })}</p>
      </div>

      <div className="panel p-5">
        <StageTrack currentStage={analysis.diagnosed_stage} />
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.4fr_0.6fr]">
        <div className="panel p-5">
          <Timeline items={items} />
          <p className="mt-5 flex items-start gap-1.5 border-t border-navy-100 pt-3 text-xs text-ink-400">
            <Info size={13} className="mt-0.5 shrink-0" />
            {t("timeline.historyNote")}
          </p>
        </div>
        <div className="grid content-start gap-4">
          {/* Progress ring summary */}
          <div className="panel flex flex-col items-center gap-2 p-5 text-center">
            <ConfidenceRing value={ringPct} size={132} tone="evidence" suffix="%" />
            <p className="text-sm text-ink-500">{t("journey.stagesReached", { reached: stagesReached, total: STAGE_ORDER.length })}</p>
          </div>
          {/* Stage-gate checklist */}
          <div className="panel p-5">
            <p className="text-overline text-ink-400">{t("journey.nextGate")}</p>
            <p className="mt-1 text-sm font-semibold text-ink-900">{label("stage", nextStage)}</p>
            <ul className="mt-3 grid gap-2">
              {gateItems.length > 0 ? (
                gateItems.map((item) => (
                  <li key={item.id} className="flex items-center gap-2 text-sm">
                    <span className={`grid h-4 w-4 shrink-0 place-items-center rounded-full ${item.done ? "bg-evidence-600 text-white" : "border border-navy-200 text-transparent"}`}>
                      {item.done ? <Check size={11} /> : <Circle size={6} />}
                    </span>
                    <span className={item.done ? "text-ink-400 line-through" : "text-ink-700"}>{item.text}</span>
                  </li>
                ))
              ) : (
                <li className="text-sm text-evidence-700">{t("journey.gateClear")}</li>
              )}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}

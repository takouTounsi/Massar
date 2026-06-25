import { motion } from "framer-motion";
import { Map, Play } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { AnomalyMoments } from "../components/AnomalyMoment";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { EvidenceLedger } from "../components/EvidenceLedger";
import { LoadingState } from "../components/LoadingState";
import { NoDiagnosisState } from "../components/NoDiagnosisState";
import { MissionHero } from "../components/MissionHero";
import { ResourceCard } from "../components/ResourceCard";
import { WeakestLinkChain } from "../components/WeakestLinkChain";
import { useProjectDashboard } from "../hooks/useProjectDashboard";
import { useRoadmap } from "../hooks/useRoadmap";
import { sectionVariants } from "../lib/anim";
import { PROVISIONAL_CONFIDENCE } from "../lib/diagnosis";
import { useI18n } from "../i18n/useI18n";

export function DashboardPage() {
  const { projectId = "" } = useParams();
  const dashboardQuery = useProjectDashboard(projectId);
  const { generateMutation } = useRoadmap(projectId);
  const { t, label } = useI18n();

  if (dashboardQuery.isLoading) return <LoadingState />;
  if (dashboardQuery.isError) return <ErrorState message={t("dashboard.loadError")} onRetry={() => dashboardQuery.refetch()} />;
  if (!dashboardQuery.data) return <EmptyState title={t("dashboard.projectNotFound")} />;

  // A freshly created project has no diagnosis until the intake runs, so
  // `analysis` (and every field below it) is null. Guard the whole component at
  // the top — every read off `analysis` would otherwise crash, not just one.
  const { project, profile, analysis } = dashboardQuery.data;
  if (!analysis) return <NoDiagnosisState projectId={projectId} />;

  const projectName = project?.name ?? profile?.name;
  const projectMeta = project ?? profile;
  const provisional =
    analysis.maturity_confidence < PROVISIONAL_CONFIDENCE || (analysis.missing_fields?.length ?? 0) > 0;

  return (
    <motion.section
      className="grid gap-5"
      initial="hidden"
      animate="visible"
      variants={{ visible: { transition: { staggerChildren: 0.06 } } }}
    >
      <motion.div custom={0} variants={sectionVariants} className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold text-ink-900">{projectName ?? "Projet Massar"}</h2>
          <p className="text-sm text-ink-500">
            {projectMeta?.region ?? label("country", projectMeta?.country)} · {projectMeta?.sector} · {t("dashboard.objective", { goal: label("goal", projectMeta?.primary_goal) })}
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => generateMutation.mutate()} disabled={generateMutation.isPending}>
          <Play size={16} /> {t("dashboard.generateRoadmap")}
        </button>
      </motion.div>

      {provisional ? (
        <motion.p custom={1} variants={sectionVariants} className="rounded-card border border-caution-100 bg-caution-50 px-4 py-2.5 text-sm text-caution-700">
          {t("diagnosis.provisionalNote")}
        </motion.p>
      ) : null}

      {/* Act I — cinematic mission control: the gap is the headline */}
      <motion.div custom={2} variants={sectionVariants}>
        <MissionHero analysis={analysis} provisional={provisional} />
      </motion.div>

      {/* Act II — the weakest link breaks the chain */}
      <motion.div custom={3} variants={sectionVariants}>
        <WeakestLinkChain analysis={analysis} projectId={projectId} />
      </motion.div>

      {/* Act III — anomaly demo moments */}
      <motion.div custom={4} variants={sectionVariants}>
        <AnomalyMoments analysis={analysis} projectId={projectId} />
      </motion.div>

      {/* Act IV — the evidence ledger */}
      <motion.div custom={5} variants={sectionVariants}>
        <EvidenceLedger analysis={analysis} />
      </motion.div>

      <motion.div custom={6} variants={sectionVariants} className="panel p-5">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="font-semibold text-ink-900">{t("dashboard.recommendedResources")}</h3>
          <Link className="text-sm font-semibold text-navy-700 hover:text-navy-600" to={`/projects/${projectId}/resources`}>
            {t("dashboard.viewAll")}
          </Link>
        </div>
        {analysis.resources.length > 0 ? (
          <div className="grid gap-3 md:grid-cols-3">
            {analysis.resources.slice(0, 3).map((resource) => (
              <ResourceCard resource={resource} key={resource.resource_id} />
            ))}
          </div>
        ) : (
          <EmptyState
            title={t("dashboard.noRoadmap")}
            action={
              <button className="btn btn-primary" onClick={() => generateMutation.mutate()}>
                <Map size={16} /> {t("dashboard.generateNow")}
              </button>
            }
          />
        )}
      </motion.div>
    </motion.section>
  );
}

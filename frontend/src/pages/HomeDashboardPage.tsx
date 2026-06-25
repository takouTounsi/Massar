import { ArrowRight, Plus, Trash2, TrendingUp, AlertTriangle, CheckCircle, Clock } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingState } from "../components/LoadingState";
import { useProject } from "../hooks/useProject";
import { useI18n } from "../i18n/useI18n";

// Mock analysis data per project — in production this comes from demo_analyses
const MOCK_ANALYSIS: Record<string, {
  diagnosed: string; declared: string; gap: string; confidence: number;
  scores: Record<string, number>; blockers: number; progress: number;
}> = {
  "11111111-1111-4111-8111-111111111111": {
    diagnosed: "MARKET_VALIDATION", declared: "FUNDRAISING", gap: "HIGH",
    confidence: 0.84, scores: { market: 38, operational: 42, innovation: 65, scalability: 35, green: 50 },
    blockers: 2, progress: 18,
  },
  "22222222-2222-4222-8222-222222222222": {
    diagnosed: "STRUCTURATION", declared: "STRUCTURATION", gap: "NONE",
    confidence: 0.78, scores: { market: 61, operational: 39, innovation: 35, scalability: 48, green: 42 },
    blockers: 1, progress: 30,
  },
  "33333333-3333-4333-8333-333333333333": {
    diagnosed: "GROWTH", declared: "LAUNCH_PLANNING", gap: "MEDIUM",
    confidence: 0.81, scores: { market: 72, operational: 64, innovation: 51, scalability: 58, green: 46 },
    blockers: 1, progress: 46,
  },
};

const GAP_CONFIG = {
  HIGH: { labelKey: "home.gapHigh", color: "#A32D2D", bg: "#FEF5F5", border: "#F9CCCC" },
  MEDIUM: { labelKey: "home.gapMedium", color: "#633806", bg: "#FEF5E4", border: "#FDDDB0" },
  NONE: { labelKey: "home.gapNone", color: "#0F6E56", bg: "#EBF7F2", border: "#9FE1CB" },
  LOW: { labelKey: "home.gapLow", color: "#5B7A1A", bg: "#F2F8E6", border: "#C5E090" },
} as const;

function MiniScoreBar({ value }: { value: number }) {
  const color = value < 45 ? "#E24B4A" : value < 60 ? "#BA7517" : "#24A07A";
  return (
    <div className="h-1 rounded-full bg-[#E8E6E2] overflow-hidden">
      <div className="h-full rounded-full transition-all duration-700" style={{ width: `${value}%`, background: color }} />
    </div>
  );
}

function ProjectCard({ project, onDelete }: { project: any; onDelete: (id: string) => void }) {
  const { t, label } = useI18n();
  const analysis = MOCK_ANALYSIS[project.project_id];
  const gap = analysis ? GAP_CONFIG[analysis.gap as keyof typeof GAP_CONFIG] ?? GAP_CONFIG.NONE : null;
  const scores = analysis ? Object.values(analysis.scores) : [];
  const avgScore = scores.length ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : null;

  return (
    <div
      className="group relative flex flex-col rounded-2xl border bg-white transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md"
      style={{ borderColor: "#E8E6E2" }}
    >
      {/* Delete button */}
      <button
        onClick={(e) => { e.preventDefault(); onDelete(project.project_id); }}
        className="absolute end-3 top-3 z-10 grid h-7 w-7 place-items-center rounded-lg border border-[#E8E6E2] bg-white opacity-0 transition group-hover:opacity-100 hover:border-red-200 hover:bg-red-50"
        title={t("home.deleteProject")}
      >
        <Trash2 size={13} className="text-red-400" />
      </button>

      <Link to={`/projects/${project.project_id}/dashboard`} className="flex flex-col flex-1 p-5">
        {/* Header */}
        <div className="flex items-start gap-3 mb-4">
          <div
            className="grid h-10 w-10 shrink-0 place-items-center rounded-xl text-white text-sm font-medium"
            style={{ background: "#0F4C35" }}
          >
            {(project.name ?? project.sector ?? "P").charAt(0).toUpperCase()}
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="font-medium text-[#1A1916] leading-snug">{project.name ?? project.sector}</h3>
            <p className="text-xs text-[#9B9994] mt-0.5">
              {label("country", project.country)} · {label("businessType", project.business_type)}
            </p>
          </div>
        </div>

        {/* Gap badge + stage */}
        {analysis && gap && (
          <div className="mb-4 flex items-center gap-2 flex-wrap">
            <span
              className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium"
              style={{ background: gap.bg, color: gap.color, border: `1px solid ${gap.border}` }}
            >
              {analysis.gap === "NONE" ? (
                <CheckCircle size={11} />
              ) : (
                <AlertTriangle size={11} />
              )}
              {t(gap.labelKey)}
            </span>
            <span className="text-xs text-[#9B9994]">
              {label("stage", analysis.diagnosed)}
            </span>
          </div>
        )}

        {/* Mini score bars */}
        {analysis && (
          <div className="space-y-2 mb-4">
            {Object.entries(analysis.scores).map(([key, val]) => (
              <div key={key} className="flex items-center gap-2">
                <span className="w-20 text-[10px] text-[#9B9994] capitalize shrink-0">{key}</span>
                <div className="flex-1">
                  <MiniScoreBar value={val} />
                </div>
                <span className="w-6 text-end text-[10px] font-medium text-[#706E69]">{val}</span>
              </div>
            ))}
          </div>
        )}

        {/* Progress bar */}
        {analysis && (
          <div className="mb-4">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[10px] text-[#9B9994] uppercase tracking-wide">{t("home.progress")}</span>
              <span className="text-[10px] font-medium text-[#706E69]">{analysis.progress}%</span>
            </div>
            <div className="h-1.5 rounded-full bg-[#E8E6E2] overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-1000"
                style={{
                  width: `${analysis.progress}%`,
                  background: "linear-gradient(90deg, #1A7A5E, #4DC49A)",
                }}
              />
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="mt-auto flex items-center justify-between pt-3 border-t border-[#F5F4F2]">
          <div className="flex items-center gap-3 text-[11px] text-[#9B9994]">
            {analysis && (
              <>
                <span className="flex items-center gap-1">
                  <AlertTriangle size={10} className="text-[#BA7517]" />
                  {analysis.blockers} {t("home.blockersWord")}
                </span>
                <span className="flex items-center gap-1">
                  <TrendingUp size={10} className="text-[#24A07A]" />
                  {avgScore}/100 {t("home.avgWord")}
                </span>
              </>
            )}
          </div>
          <span className="flex items-center gap-1 text-xs font-medium text-[#1A7A5E]">
            {t("home.open")} <ArrowRight size={13} />
          </span>
        </div>
      </Link>
    </div>
  );
}

export function HomeDashboardPage() {
  const { projectsQuery } = useProject();
  const { t } = useI18n();
  const [deletedIds, setDeletedIds] = useState<Set<string>>(new Set());

  if (projectsQuery.isLoading) return <LoadingState />;
  if (projectsQuery.isError) return <ErrorState message={t("dashboard.loadError")} onRetry={() => projectsQuery.refetch()} />;

  const allProjects = projectsQuery.data ?? [];
  const projects = allProjects.filter((p) => !deletedIds.has(p.project_id));

  const handleDelete = (id: string) => {
    if (window.confirm(t("home.deleteConfirm"))) {
      setDeletedIds((prev) => new Set([...prev, id]));
    }
  };

  // Summary stats
  const totalBlockers = projects.reduce((sum, p) => sum + (MOCK_ANALYSIS[p.project_id]?.blockers ?? 0), 0);
  const avgProgress = projects.length
    ? Math.round(projects.reduce((sum, p) => sum + (MOCK_ANALYSIS[p.project_id]?.progress ?? 0), 0) / projects.length)
    : 0;
  const aligned = projects.filter((p) => MOCK_ANALYSIS[p.project_id]?.gap === "NONE").length;

  return (
    <section className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.1em] text-[#9B9994] mb-1">{t("home.workspace")}</p>
          <h2 className="text-2xl font-medium text-[#1A1916]">{t("home.myProjects")}</h2>
          <p className="text-sm text-[#706E69] mt-1">
            {projects.length} {t("home.projectsWord")} · {t("home.diagnosticActive")}
          </p>
        </div>
        <Link
          to="/projects/new"
          className="inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium text-white transition hover:opacity-90"
          style={{ background: "#0F4C35" }}
        >
          <Plus size={16} />
          {t("home.newProject")}
        </Link>
      </div>

      {/* Summary strip */}
      {projects.length > 0 && (
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: t("home.statActive"), value: projects.length, icon: <Clock size={14} />, color: "#1A7A5E" },
            { label: t("home.statBlockers"), value: totalBlockers, icon: <AlertTriangle size={14} />, color: "#BA7517" },
            { label: t("home.statProgress"), value: `${avgProgress}%`, icon: <TrendingUp size={14} />, color: "#24A07A" },
          ].map((stat) => (
            <div
              key={stat.label}
              className="flex items-center gap-3 rounded-xl border border-[#E8E6E2] bg-white px-4 py-3"
            >
              <span style={{ color: stat.color }}>{stat.icon}</span>
              <div>
                <p className="text-lg font-medium text-[#1A1916]">{stat.value}</p>
                <p className="text-xs text-[#9B9994]">{stat.label}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Project grid */}
      {projects.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-[#D4D2CE] p-16 text-center">
          <div className="mx-auto mb-4 grid h-12 w-12 place-items-center rounded-xl" style={{ background: "#EBF7F2" }}>
            <Plus size={22} className="text-[#1A7A5E]" />
          </div>
          <h3 className="font-medium text-[#1A1916] mb-1">{t("home.noProject")}</h3>
          <p className="text-sm text-[#9B9994] mb-4">{t("home.emptyHint")}</p>
          <Link
            to="/projects/new"
            className="inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium text-white"
            style={{ background: "#0F4C35" }}
          >
            <Plus size={15} /> {t("home.createProject")}
          </Link>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {projects.map((project) => (
            <ProjectCard key={project.project_id} project={project} onDelete={handleDelete} />
          ))}

          {/* Add project tile */}
          <Link
            to="/projects/new"
            className="flex min-h-[200px] flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-[#D4D2CE] text-center transition hover:border-[#1A7A5E] hover:bg-[#EBF7F2] group"
          >
            <div className="grid h-10 w-10 place-items-center rounded-xl border border-[#D4D2CE] group-hover:border-[#9FE1CB] group-hover:bg-white">
              <Plus size={18} className="text-[#9B9994] group-hover:text-[#1A7A5E]" />
            </div>
            <p className="text-sm text-[#9B9994] group-hover:text-[#1A7A5E] font-medium">{t("home.addProject")}</p>
          </Link>
        </div>
      )}
    </section>
  );
}
import { BarChart3, BrainCircuit, Compass, FolderPlus, Gauge, Layers, LogOut, Map, Route, ShieldCheck, Target, UsersRound } from "lucide-react";
import { NavLink, Outlet, useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { useProject } from "../hooks/useProject";
import { useProjectDashboard } from "../hooks/useProjectDashboard";
import { gapTone } from "../lib/diagnosis";
import { useI18n } from "../i18n/useI18n";
import { LanguageSwitcher } from "./LanguageSwitcher";
import { StageRail } from "./StageRail";

const GAP_CHIP: Record<string, string> = {
  evidence: "bg-evidence-50 text-evidence-700",
  caution: "bg-caution-50 text-caution-700",
  flag: "bg-flag-50 text-flag-700"
};

export function AppLayout() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const auth = useAuth();
  const { activeProject } = useProject(projectId);
  const { t, label, text } = useI18n();
  const activeId = projectId ?? activeProject?.project_id;
  const dashboardQuery = useProjectDashboard(projectId ? activeId ?? "" : "");
  const analysis = dashboardQuery.data?.analysis;
  const links = [
    { to: "/dashboard", label: t("layout.dashboard"), icon: BarChart3 },
    { to: "/projects/new", label: t("layout.myProject"), icon: FolderPlus },
    ...(activeId
      ? [
          { to: `/projects/${activeId}/dashboard`, label: t("layout.diagnostic"), icon: Target },
          { to: `/projects/${activeId}/scores`, label: t("layout.scores"), icon: Layers },
          { to: `/projects/${activeId}/roadmap`, label: t("layout.roadmap"), icon: Map },
          { to: `/projects/${activeId}/resources`, label: t("layout.resources"), icon: UsersRound },
          { to: `/projects/${activeId}/intelligence`, label: t("layout.intelligence"), icon: BrainCircuit },
          { to: `/projects/${activeId}/journey`, label: t("layout.journey"), icon: Route }
        ]
      : []),
    { to: "/settings/security", label: t("layout.security"), icon: ShieldCheck }
  ];

  return (
    <div className="min-h-screen bg-paper">
      <aside className="panel-navy fixed inset-y-0 start-0 z-20 hidden w-64 rounded-none p-4 md:block">
        <div className="mb-8 flex items-center gap-2.5">
          <span className="grid h-9 w-9 place-items-center rounded-lg bg-flag-600 text-white">
            <Compass size={20} />
          </span>
          <div>
            <p className="text-overline font-semibold uppercase text-navy-200">Massar</p>
            <h1 className="text-sm font-semibold text-white">{t("layout.product")}</h1>
          </div>
        </div>
        <nav className="grid gap-1">
          {links.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink className={({ isActive }) => `sidebar-link ${isActive ? "sidebar-link-active" : ""}`} to={item.to} key={item.to}>
                <Icon size={17} /> {item.label}
              </NavLink>
            );
          })}
        </nav>
      </aside>
      <div className="md:ps-64">
        <header className="sticky top-0 z-10 border-b border-navy-100 bg-white/95 backdrop-blur">
          <div className="flex items-center justify-between gap-4 px-4 py-3">
            <div className="min-w-0">
              <p className="overline">{t("layout.activeProject")}</p>
              <div className="flex items-center gap-2">
                <p className="truncate font-semibold text-ink-900">{activeProject?.name ?? t("layout.noProject")}</p>
                {activeProject?.sector ? (
                  <span className="chip shrink-0 bg-navy-50 font-medium text-navy-700">{text(activeProject.sector)}</span>
                ) : null}
              </div>
            </div>
            <div className="flex items-center gap-3">
              {analysis ? (
                <div className="hidden items-center gap-2 sm:flex">
                  <span className="chip bg-evidence-50 font-medium text-evidence-700">
                    <Gauge size={13} /> {t("header.readiness", { value: Math.round(analysis.progress) })}
                  </span>
                  {analysis.declared_stage !== analysis.diagnosed_stage ? (
                    <span className={`chip font-medium ${GAP_CHIP[gapTone(analysis.gap_level)]}`}>
                      {label("stage", analysis.declared_stage)} → {label("stage", analysis.diagnosed_stage)} · {t("gap.level", { gap: label("gap", analysis.gap_level) })}
                    </span>
                  ) : null}
                </div>
              ) : null}
              <LanguageSwitcher />
              <div className="text-end">
                <p className="text-sm font-medium text-ink-900">{auth.user?.full_name ?? t("layout.session")}</p>
                <p className="text-xs text-evidence-700">{t("layout.activeSession")}</p>
              </div>
              <button
                className="btn btn-secondary"
                onClick={() => {
                  auth.logoutMutation.mutate(undefined, { onSuccess: () => navigate("/login") });
                }}
              >
                <LogOut size={16} /> {t("layout.logout")}
              </button>
            </div>
          </div>
          {projectId && analysis ? <StageRail diagnosedStage={analysis.diagnosed_stage} declaredStage={analysis.declared_stage} /> : null}
        </header>
        <main className="mx-auto max-w-7xl px-4 py-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

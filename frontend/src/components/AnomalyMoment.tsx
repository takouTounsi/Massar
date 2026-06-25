import { AlertOctagon, ArrowDown, ChevronDown, Lightbulb, Radar, Target, TrendingDown } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import type { DemoBlocker, DashboardAnalysis } from "../api/types";
import { buildCausalChain, orderedBlockers, scoreTone } from "../lib/diagnosis";
import { useI18n } from "../i18n/useI18n";
import { CitationChip } from "./CitationChip";

function Moment({
  blocker,
  analysis,
  projectId,
  open,
  onToggle
}: {
  blocker: DemoBlocker;
  analysis: DashboardAnalysis;
  projectId: string;
  open: boolean;
  onToggle: () => void;
}) {
  const { t, label, text } = useI18n();
  const chain = buildCausalChain(analysis, blocker);

  return (
    <div
      className={`relative overflow-hidden rounded-card border bg-white transition duration-300 ${
        open ? "border-flag-400 shadow-glow-flag" : "border-flag-200 hover:border-flag-400 hover:shadow-glow-flag"
      }`}
    >
      {/* red scan-line sweep on expand */}
      {open ? <span aria-hidden className="pointer-events-none absolute inset-x-0 top-0 z-10 h-12 animate-scan bg-gradient-to-b from-flag-600/30 to-transparent" /> : null}

      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-start focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-flag-400"
      >
        <span className="flex items-center gap-2.5">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-flag-50 text-flag-600">
            <AlertOctagon size={17} />
          </span>
          <span>
            <span className="block text-sm font-semibold text-ink-900">{label("blocker", blocker.type)}</span>
            <span className="block text-xs text-flag-700">{t("anomaly.demoMoment")}</span>
          </span>
        </span>
        <span className="flex items-center gap-2">
          <span className="hidden text-xs font-semibold text-flag-700 sm:inline">{open ? t("anomaly.collapse") : t("anomaly.expand")}</span>
          <ChevronDown size={18} className={`text-flag-500 transition-transform duration-300 ${open ? "rotate-180" : ""}`} />
        </span>
      </button>

      {open ? (
        <div className="animate-rise space-y-3 border-t border-flag-100 px-4 py-4">
          <div className="relative ps-7">
            <span className="absolute start-0 top-0.5 grid h-5 w-5 place-items-center rounded-full bg-flag-50 text-flag-600"><Target size={12} /></span>
            <p className="text-overline text-flag-700">{t("gap.title")}</p>
            <ul className="mt-1 space-y-0.5 text-sm text-ink-700">
              {blocker.evidence.map((item, idx) => (
                <li key={idx}>{text(item)}</li>
              ))}
            </ul>
          </div>

          <ArrowDown size={14} className="ms-1.5 text-flag-400" />
          <div className="relative ps-7">
            <span className="absolute start-0 top-0.5 grid h-5 w-5 place-items-center rounded-full bg-flag-50 text-flag-600"><TrendingDown size={12} /></span>
            <p className="text-overline text-flag-700">{t("causal.lowered")}</p>
            <div className="mt-1 flex flex-wrap gap-1.5">
              {chain.scores.length > 0 ? (
                chain.scores.map((score) => {
                  const value = analysis.scores[score];
                  const tone = value != null ? scoreTone(value) : "caution";
                  return (
                    <span key={score} className={`chip ${tone === "flag" ? "bg-flag-50 text-flag-700" : tone === "caution" ? "bg-caution-50 text-caution-700" : "bg-evidence-50 text-evidence-700"}`}>
                      {label("score", score)}
                      {value != null ? <span className="tabular-nums">· {Math.round(value)}</span> : null}
                    </span>
                  );
                })
              ) : (
                <span className="text-sm text-ink-400">—</span>
              )}
            </div>
          </div>

          <ArrowDown size={14} className="ms-1.5 text-evidence-400" />
          <div className="relative ps-7">
            <span className="absolute start-0 top-0.5 grid h-5 w-5 place-items-center rounded-full bg-evidence-50 text-evidence-600"><Lightbulb size={12} /></span>
            <p className="text-overline text-evidence-700">{t("causal.fix")}</p>
            {chain.fix ? (
              <div className="mt-1 rounded-lg border border-evidence-100 bg-evidence-50/50 p-3">
                <p className="text-sm font-semibold text-ink-900">{text(chain.fix.title)}</p>
                <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                  {chain.resources.map((r) => (
                    <CitationChip key={r.resource_id} url={r.source_url} label={r.institution} />
                  ))}
                  <Link className="text-sm font-semibold text-navy-700 hover:text-navy-600" to={`/projects/${projectId}/roadmap`}>
                    {t("dashboard.viewRoadmap")} →
                  </Link>
                </div>
              </div>
            ) : (
              <p className="mt-1 text-sm text-caution-700">{t("causal.noFix")}</p>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}

/** Stage-blocking contradictions surfaced as expandable, red-glowing demo moments. */
export function AnomalyMoments({ analysis, projectId }: { analysis: DashboardAnalysis; projectId: string }) {
  const { t } = useI18n();
  const anomalies = orderedBlockers(analysis.blockers).filter((b) => b.stage_blocking);
  const [openId, setOpenId] = useState<string | null>(null);

  if (anomalies.length === 0) return null;

  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <Radar size={18} className="text-flag-600" />
        <h3 className="font-semibold text-ink-900">{t("anomaly.sectionTitle")}</h3>
      </div>
      <div className="grid gap-2.5">
        {anomalies.map((blocker) => (
          <Moment
            key={blocker.id}
            blocker={blocker}
            analysis={analysis}
            projectId={projectId}
            open={openId === blocker.id}
            onToggle={() => setOpenId((cur) => (cur === blocker.id ? null : blocker.id))}
          />
        ))}
      </div>
    </div>
  );
}

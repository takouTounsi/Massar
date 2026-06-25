import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, ChevronDown, GitPullRequestArrow } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import type { DashboardAnalysis } from "../api/types";
import { buildScoreChain, scoreTone, weakestScore } from "../lib/diagnosis";
import { useI18n } from "../i18n/useI18n";

const TONE_COST: Record<string, string> = {
  evidence: "text-evidence-700",
  caution: "text-caution-700",
  flag: "text-flag-700"
};

/**
 * Bottleneck chain: the weak dimensions that hold readiness down, each showing
 * how it drags the weakest link and what it costs. Mirrors the engine's
 * `BottleneckAnalysis`; derived from live scores until that report is wired.
 */
export function BottleneckAccordion({ analysis, projectId }: { analysis: DashboardAnalysis; projectId: string }) {
  const { t, label, text } = useI18n();
  const [open, setOpen] = useState<string | null>(null);
  const weakest = weakestScore(analysis.scores);
  const entries = Object.entries(analysis.scores)
    .filter(([, v]) => v < 55)
    .sort((a, b) => a[1] - b[1]);

  if (entries.length === 0) {
    return <p className="rounded-card border border-evidence-100 bg-evidence-50/50 px-4 py-3 text-sm text-evidence-700">{t("bottleneck.none")}</p>;
  }

  return (
    <div className="grid gap-2">
      {entries.map(([name, value]) => {
        const tone = scoreTone(value);
        const chain = buildScoreChain(analysis, name);
        // readiness cost ≈ how far this dimension sits below a healthy 60, weighted
        const cost = Math.round((Math.max(0, 60 - value) * 0.25) * 10) / 10;
        const isOpen = open === name;
        return (
          <div key={name} className="overflow-hidden rounded-card border border-navy-100 bg-white">
            <button
              type="button"
              onClick={() => setOpen((cur) => (cur === name ? null : name))}
              aria-expanded={isOpen}
              className="flex w-full items-center gap-3 px-4 py-3 text-start focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-400"
            >
              <span className="chip bg-navy-50 text-[10px] text-navy-700">{t("bottleneck.dimension")}</span>
              <span className="flex min-w-0 flex-1 items-center gap-1.5 text-sm font-medium text-ink-900">
                <span className="truncate">{label("score", name)}</span>
                {name !== weakest && weakest ? (
                  <>
                    <ArrowRight size={13} className="shrink-0 text-ink-400" />
                    <span className="truncate text-ink-500">{label("score", weakest)}</span>
                  </>
                ) : null}
              </span>
              <span className={`shrink-0 text-sm font-semibold tabular-nums ${TONE_COST[tone]}`}>−{cost}</span>
              <ChevronDown size={16} className={`shrink-0 text-ink-400 transition-transform duration-300 ${isOpen ? "rotate-180" : ""}`} />
            </button>
            <AnimatePresence initial={false}>
              {isOpen ? (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.2, ease: "easeOut" }}
                  className="overflow-hidden"
                >
                  <div className="space-y-2 border-t border-navy-100 px-4 py-3 text-sm text-ink-600">
                    <p>{t("bottleneck.explain", { score: label("score", name), value: Math.round(value) })}</p>
                    <p className="text-ink-500">{t("bottleneck.firstThings")}</p>
                    {chain.fix ? (
                      <Link className="inline-flex items-center gap-1.5 font-semibold text-navy-700 hover:text-navy-600" to={`/projects/${projectId}/roadmap`}>
                        <GitPullRequestArrow size={14} /> {text(chain.fix.title)}
                      </Link>
                    ) : (
                      <Link className="inline-flex items-center gap-1.5 font-semibold text-navy-700 hover:text-navy-600" to={`/projects/${projectId}/roadmap`}>
                        {t("dashboard.viewRoadmap")} →
                      </Link>
                    )}
                  </div>
                </motion.div>
              ) : null}
            </AnimatePresence>
          </div>
        );
      })}
    </div>
  );
}

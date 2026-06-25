import { ArrowDown, Link2Off, Lightbulb, TrendingDown, Zap } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import type { DashboardAnalysis } from "../api/types";
import { buildScoreChain, orderedScores, scoreTone, weakestScore } from "../lib/diagnosis";
import { useCountUp, useInViewOnce } from "../lib/motion";
import { useI18n } from "../i18n/useI18n";
import { CitationChip } from "./CitationChip";

const TONE_RING: Record<string, string> = {
  evidence: "border-evidence-400 text-evidence-700",
  caution: "border-caution-400 text-caution-700",
  flag: "border-flag-600 text-flag-700"
};

function ScoreLink({
  name,
  value,
  isWeakest,
  selected,
  active,
  onSelect
}: {
  name: string;
  value: number;
  isWeakest: boolean;
  selected: boolean;
  active: boolean;
  onSelect: () => void;
}) {
  const { label } = useI18n();
  const animated = useCountUp(Math.round(value), active, 900);
  const tone = scoreTone(value);

  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={`group relative flex min-w-[104px] flex-1 flex-col items-center gap-1 rounded-xl border-2 bg-white px-3 py-3 transition duration-300 ease-sovereign focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-400 ${
        TONE_RING[tone]
      } ${selected ? "shadow-trust-lg" : "hover:-translate-y-0.5 hover:shadow-trust"} ${isWeakest ? "animate-pulse-glow" : ""}`}
    >
      {isWeakest ? (
        <span className="absolute -top-2 inline-flex items-center gap-1 rounded-full bg-flag-600 px-2 py-0.5 text-[9px] font-bold uppercase text-white shadow-glow-flag">
          <Link2Off size={9} /> λ
        </span>
      ) : null}
      <span className="text-2xl font-bold tabular-nums text-ink-900">{Math.round(animated)}</span>
      <span className="text-center text-[11px] font-semibold leading-tight">{label("score", name)}</span>
    </button>
  );
}

/**
 * The scores rendered as a literal chain whose weakest link pulses red. Click it
 * to reveal the λ causal chain: score → dragged down by → composite penalty →
 * recommended program. This is the demo's "weakest-link, never averages" moment.
 */
export function WeakestLinkChain({ analysis, projectId }: { analysis: DashboardAnalysis; projectId: string }) {
  const { t, label, text } = useI18n();
  const { ref, inView } = useInViewOnce<HTMLDivElement>();
  const weakest = weakestScore(analysis.scores);
  const [selected, setSelected] = useState<string | null>(weakest);
  const scores = orderedScores(analysis.scores);

  const active = selected ?? weakest;
  const chain = active ? buildScoreChain(analysis, active) : null;
  const activeValue = active ? Math.round(analysis.scores[active]) : 0;

  return (
    <div ref={ref} className="panel p-5">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Zap size={18} className="text-flag-600" />
          <h3 className="font-semibold text-ink-900">{t("weaklink.title")}</h3>
        </div>
        <Link className="shrink-0 text-sm font-semibold text-navy-700 hover:text-navy-600" to={`/projects/${projectId}/scores`}>
          {t("scores.viewFull")} →
        </Link>
      </div>
      <p className="mt-1 text-sm text-ink-500">{t("weaklink.subtitle")}</p>

      {/* The chain */}
      <div className="mt-5 flex flex-wrap items-stretch gap-2">
        {scores.map(([name, value], idx) => (
          <div key={name} className="flex flex-1 items-center gap-2">
            <ScoreLink
              name={name}
              value={value}
              isWeakest={name === weakest}
              selected={active === name}
              active={inView}
              onSelect={() => setSelected(name)}
            />
            {idx < scores.length - 1 ? (
              <span className={`hidden h-0.5 w-3 shrink-0 sm:block ${name === weakest || scores[idx + 1][0] === weakest ? "bg-flag-300" : "bg-navy-200"}`} />
            ) : null}
          </div>
        ))}
      </div>

      {/* The λ causal reveal */}
      {active && chain ? (
        <div key={active} className="mt-6 animate-rise space-y-3 rounded-card border border-flag-100 bg-flag-50/30 p-4">
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold text-ink-900">{label("score", active)}</span>
            <span className="chip bg-flag-600 text-[11px] text-white">{activeValue}/100</span>
          </div>

          <ArrowDown size={14} className="text-flag-400" />
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wide text-flag-700">{t("weaklink.draggedDown")}</p>
            <div className="mt-1 flex flex-wrap gap-1.5">
              {chain.weakSubScores.length > 0 ? (
                chain.weakSubScores.map((item) => (
                  <span key={item} className="chip bg-white text-[11px] text-caution-700 shadow-trust">
                    <TrendingDown size={11} /> {label("weakSignal", item)}
                  </span>
                ))
              ) : (
                <span className="text-sm text-ink-400">—</span>
              )}
            </div>
          </div>

          <ArrowDown size={14} className="text-flag-400" />
          <div className="rounded-lg border border-flag-200 bg-white p-3">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-flag-700">{t("weaklink.causes")}</p>
            <p className="mt-0.5 text-sm font-semibold text-ink-900">
              {t("weaklink.penalty")} · {t("weaklink.composite")} {activeValue}/100
            </p>
            <p className="mt-0.5 text-sm text-ink-600">{t("weaklink.penaltyExplain")}</p>
          </div>

          <ArrowDown size={14} className="text-evidence-400" />
          <div className="rounded-lg border border-evidence-100 bg-evidence-50/60 p-3">
            <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-evidence-700">
              <Lightbulb size={12} /> {t("weaklink.recommended")}
            </p>
            {chain.fix ? (
              <div className="mt-1">
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
              <p className="mt-1 text-sm text-caution-700">{t("weaklink.noProgram")}</p>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}

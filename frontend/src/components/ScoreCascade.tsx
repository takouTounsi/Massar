import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { AlertTriangle, ArrowDown, ChevronDown, Lightbulb, Link2Off, TrendingDown } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import type { DashboardAnalysis } from "../api/types";
import { sectionVariants } from "../lib/anim";
import { buildScoreChain, scoreTone, weakestScore } from "../lib/diagnosis";
import { estimateLambda } from "../lib/intelligence";
import { useCountUp, useInViewOnce } from "../lib/motion";
import { useI18n } from "../i18n/useI18n";
import { CitationChip } from "./CitationChip";
import { LambdaTooltip } from "./LambdaTooltip";

const TONE_ACCENT: Record<string, string> = {
  evidence: "border-s-evidence-500",
  caution: "border-s-caution-500",
  flag: "border-s-flag-600"
};
const TONE_BAR: Record<string, string> = {
  evidence: "bg-evidence-500",
  caution: "bg-caution-500",
  flag: "bg-flag-600"
};
const TONE_TEXT: Record<string, string> = {
  evidence: "text-evidence-700",
  caution: "text-caution-700",
  flag: "text-flag-700"
};

/** Animated SVG connector that draws downward between two score rows. */
function Connector({ active }: { active: boolean }) {
  const reduced = useReducedMotion();
  return (
    <div className="flex h-6 justify-center" aria-hidden>
      <svg width="14" height="24" viewBox="0 0 14 24" fill="none">
        <motion.path
          d="M7 0 L7 18"
          stroke="var(--navy-200)"
          strokeWidth="1.5"
          initial={{ pathLength: reduced ? 1 : 0 }}
          animate={{ pathLength: active ? 1 : 0 }}
          transition={{ duration: 0.4, ease: "easeOut" }}
        />
        <path d="M3 15 L7 20 L11 15" stroke="var(--navy-200)" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </div>
  );
}

function ScoreRow({
  name,
  value,
  index,
  isWeakest,
  hasAnomaly,
  analysis,
  projectId,
  active,
  open,
  onToggle
}: {
  name: string;
  value: number;
  index: number;
  isWeakest: boolean;
  hasAnomaly: boolean;
  analysis: DashboardAnalysis;
  projectId: string;
  active: boolean;
  open: boolean;
  onToggle: () => void;
}) {
  const { t, label, text } = useI18n();
  const tone = scoreTone(value);
  const rounded = Math.round(value);
  const animated = useCountUp(rounded, active, 900);
  const chain = buildScoreChain(analysis, name);
  const est = estimateLambda(analysis, name);

  return (
    <motion.div
      custom={index}
      variants={sectionVariants}
      className={`rounded-card border border-s-2 bg-white ${TONE_ACCENT[tone]} ${isWeakest ? "animate-pulse-glow" : "border-navy-100"}`}
    >
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full items-center gap-4 px-4 py-3.5 text-start focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-400"
      >
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold text-ink-900">{label("score", name)}</span>
            {est.penalized ? <LambdaTooltip analysis={analysis} scoreKey={name} /> : null}
            {isWeakest ? (
              <span className="chip bg-flag-600 text-[10px] text-white">
                <Link2Off size={10} /> {t("scores.weakestLink")}
              </span>
            ) : null}
            {hasAnomaly ? (
              <span className="chip bg-flag-50 text-[10px] text-flag-700">
                <AlertTriangle size={10} /> {t("scores.anomaly")}
              </span>
            ) : null}
          </div>
          <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-navy-100">
            <motion.div
              className={`h-full rounded-full ${TONE_BAR[tone]}`}
              initial={{ width: 0 }}
              animate={{ width: active ? `${rounded}%` : 0 }}
              transition={{ duration: 0.5, ease: "easeOut", delay: index * 0.12 }}
            />
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className={`text-xl font-semibold tabular-nums ${TONE_TEXT[tone]}`}>{Math.round(animated)}</span>
          <span className="text-xs text-ink-400">/100</span>
          <ChevronDown size={16} className={`text-ink-400 transition-transform duration-300 ${open ? "rotate-180" : ""}`} />
        </div>
      </button>

      <AnimatePresence initial={false}>
        {open ? (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="overflow-hidden"
          >
            <div className="space-y-3 border-t border-navy-100 px-4 py-4">
              {/* dragged down by */}
              <div>
                <p className="text-overline text-flag-700">{t("scores.draggedBy")}</p>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {chain.weakSubScores.length > 0 ? (
                    chain.weakSubScores.map((item) => (
                      <span key={item} className="chip bg-caution-50 text-[11px] text-caution-700">
                        <TrendingDown size={11} /> {label("weakSignal", item)}
                      </span>
                    ))
                  ) : (
                    <span className="text-sm text-ink-400">{t("scores.noWeakSignal")}</span>
                  )}
                </div>
              </div>

              {/* λ-penalty box */}
              {est.penalized ? (
                <div className="rounded-lg border border-flag-200 bg-flag-50/40 p-3">
                  <p className="text-overline text-flag-700">{t("lambda.title")}</p>
                  <p className="mt-1 font-mono text-xs text-ink-700">
                    C = {est.cBase} × (1 − {est.lambda} × (1 − x<sub>min</sub>)) = <span className="font-semibold text-flag-700">{est.composite}</span>
                  </p>
                  <p className="mt-1 text-[11px] text-ink-500">{t("lambda.explainShort", { base: est.cBase, final: est.composite })}</p>
                </div>
              ) : null}

              {/* highest-leverage action */}
              <div className="rounded-lg border border-gold-300 bg-gold-50 p-3">
                <p className="flex items-center gap-1.5 text-overline text-[#8B6914]">
                  <Lightbulb size={12} /> {t("scores.leverageAction")}
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
          </motion.div>
        ) : null}
      </AnimatePresence>
    </motion.div>
  );
}

/**
 * The weakest-link cascade: the five scores stacked weakest→strongest, each a
 * causal link in a chain whose floor is set by the weakest. The weakest pulses
 * red; SVG connectors draw the "causes" relationship downward; every row
 * expands to its λ-penalty math and highest-leverage fix.
 */
export function ScoreCascade({
  analysis,
  projectId,
  initialDim
}: {
  analysis: DashboardAnalysis;
  projectId: string;
  initialDim?: string | null;
}) {
  const { ref, inView } = useInViewOnce<HTMLDivElement>();
  const reduced = useReducedMotion();
  const active = inView || Boolean(reduced);
  const weakest = weakestScore(analysis.scores);
  const ordered = Object.entries(analysis.scores).sort((a, b) => a[1] - b[1]);
  const hasStageBlocker = analysis.blockers.some((b) => b.stage_blocking);
  const [open, setOpen] = useState<string | null>(initialDim ?? weakest);

  return (
    <motion.div
      ref={ref}
      initial="hidden"
      animate={active ? "visible" : "hidden"}
      variants={{ visible: { transition: { staggerChildren: 0.12 } } }}
    >
      {ordered.map(([name, value], idx) => (
        <div key={name}>
          <ScoreRow
            name={name}
            value={value}
            index={idx}
            isWeakest={name === weakest}
            hasAnomaly={name === weakest && hasStageBlocker}
            analysis={analysis}
            projectId={projectId}
            active={active}
            open={open === name}
            onToggle={() => setOpen((cur) => (cur === name ? null : name))}
          />
          {idx < ordered.length - 1 ? <Connector active={active} /> : null}
        </div>
      ))}
    </motion.div>
  );
}

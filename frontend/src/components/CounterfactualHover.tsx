import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import { projectActionImpact } from "../lib/intelligence";
import { useI18n } from "../i18n/useI18n";

/**
 * Floating "if you complete this" preview shown on roadmap-node hover. Renders
 * projected score deltas + readiness gain so the strategy game feels real.
 * Numbers are estimates (see projectActionImpact) and labelled as projected.
 */
export function CounterfactualHover({
  open,
  scores,
  improvesScores,
  estimatedEffort
}: {
  open: boolean;
  scores: Record<string, number>;
  improvesScores: string[];
  estimatedEffort?: string;
}) {
  const { t, label } = useI18n();
  const { deltas, readinessGain } = projectActionImpact(scores, improvesScores, estimatedEffort);
  if (deltas.length === 0) return null;

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          role="tooltip"
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 6 }}
          transition={{ duration: 0.15 }}
          className="absolute bottom-full start-0 z-30 mb-2 w-60 rounded-card border border-navy-100 bg-white p-3 shadow-trust-lg"
        >
          <p className="text-overline text-evidence-700">{t("counterfactual.title")}</p>
          <ul className="mt-2 space-y-1">
            {deltas.map((d) => (
              <li key={d.score} className="flex items-center justify-between gap-2 text-xs">
                <span className="truncate text-ink-600">{label("score", d.score)}</span>
                <span className="flex items-center gap-1 tabular-nums text-ink-900">
                  {d.before} <ArrowRight size={11} className="text-ink-400" /> {d.after}
                  <span className="font-semibold text-evidence-700">(+{d.delta})</span>
                </span>
              </li>
            ))}
            <li className="flex items-center justify-between gap-2 border-t border-navy-100 pt-1 text-xs">
              <span className="text-ink-600">{t("counterfactual.readiness")}</span>
              <span className="font-semibold tabular-nums text-evidence-700">+{readinessGain}</span>
            </li>
          </ul>
          <p className="mt-2 text-[10px] leading-tight text-ink-400">{t("counterfactual.projected")}</p>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

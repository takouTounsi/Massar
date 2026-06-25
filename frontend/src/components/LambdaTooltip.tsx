import { AnimatePresence, motion } from "framer-motion";
import { HelpCircle } from "lucide-react";
import { useState } from "react";
import type { ScoreDecomposition } from "../api/intelligence";
import type { DashboardAnalysis } from "../api/types";
import { estimateLambda } from "../lib/intelligence";
import { useI18n } from "../i18n/useI18n";

/**
 * The judge-demo "?" beside a penalized score. On hover/focus it reveals the
 * weakest-link math: pre-penalty base → λ factor → final composite.
 *
 * If a real `ScoreDecomposition` is supplied it shows exact engine numbers;
 * otherwise it shows an estimate derived from the documented λ rule, labelled
 * as such.
 */
export function LambdaTooltip({
  analysis,
  scoreKey,
  decomposition
}: {
  analysis: DashboardAnalysis;
  scoreKey: string;
  decomposition?: ScoreDecomposition;
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);

  const exact = Boolean(decomposition);
  const est = estimateLambda(analysis, scoreKey);
  const composite = decomposition ? Math.round(decomposition.composite_value) : est.composite;
  const cBase = decomposition ? Math.round(decomposition.c_base) : est.cBase;
  const factor = decomposition
    ? 1 - decomposition.lambda_penalty_fraction
    : est.factor;

  return (
    <span className="relative inline-flex">
      <button
        type="button"
        aria-label={t("lambda.title")}
        className="text-ink-400 transition-colors hover:text-flag-600 focus-visible:outline-none focus-visible:text-flag-600"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
      >
        <HelpCircle size={14} />
      </button>
      <AnimatePresence>
        {open ? (
          <motion.span
            role="tooltip"
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 4 }}
            transition={{ duration: 0.15 }}
            className="absolute bottom-full start-1/2 z-30 mb-2 w-56 -translate-x-1/2 rounded-card border border-navy-100 bg-white p-3 text-start shadow-trust-lg rtl:translate-x-1/2"
          >
            <p className="text-overline text-flag-700">{t("lambda.title")}</p>
            <dl className="mt-2 space-y-1 text-xs">
              <div className="flex items-center justify-between gap-2">
                <dt className="text-ink-500">{t("lambda.without")}</dt>
                <dd className="font-semibold tabular-nums text-ink-900">{cBase}</dd>
              </div>
              <div className="flex items-center justify-between gap-2">
                <dt className="text-ink-500">{t("lambda.applied")}</dt>
                <dd className="font-semibold tabular-nums text-flag-700">×{factor.toFixed(2)}</dd>
              </div>
              <div className="flex items-center justify-between gap-2 border-t border-navy-100 pt-1">
                <dt className="text-ink-700">{t("lambda.final")}</dt>
                <dd className="font-semibold tabular-nums text-ink-900">{composite}</dd>
              </div>
            </dl>
            {!exact ? <p className="mt-2 text-[10px] leading-tight text-ink-400">{t("lambda.estimate")}</p> : null}
          </motion.span>
        ) : null}
      </AnimatePresence>
    </span>
  );
}

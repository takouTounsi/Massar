import { motion, useReducedMotion } from "framer-motion";
import { STAGE_ORDER, stageIndex } from "../lib/diagnosis";
import { useI18n } from "../i18n/useI18n";

/**
 * Persistent six-stage progress rail, pinned under the header so founders
 * always know where they stand. The diagnosed stage is filled; earlier stages
 * are solid, later stages hollow. The declared stage (if it differs) gets a
 * ring so the perception–reality gap stays visible everywhere.
 *
 * Uses logical inset properties so it mirrors in RTL.
 */
export function StageRail({
  diagnosedStage,
  declaredStage
}: {
  diagnosedStage: string;
  declaredStage?: string;
}) {
  const { label } = useI18n();
  const reduced = useReducedMotion();
  const n = STAGE_ORDER.length;
  const diagnosedIdx = Math.max(0, stageIndex(diagnosedStage));
  const declaredIdx = declaredStage ? stageIndex(declaredStage) : -1;
  const fillPct = (diagnosedIdx / (n - 1)) * 100;

  return (
    <div className="border-b border-navy-100 bg-white px-4 py-2">
      <div className="relative mx-auto flex max-w-7xl items-center">
        {/* base line */}
        <div className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-navy-100" />
        {/* filled line up to diagnosed */}
        <motion.div
          className="absolute top-1/2 h-px -translate-y-1/2 bg-evidence-600"
          style={{ insetInlineStart: 0 }}
          initial={{ width: reduced ? `${fillPct}%` : 0 }}
          animate={{ width: `${fillPct}%` }}
          transition={{ duration: 0.7, ease: "easeOut" }}
        />
        <ol className="relative flex w-full items-center justify-between">
          {STAGE_ORDER.map((stage, idx) => {
            const reached = idx <= diagnosedIdx;
            const isDiagnosed = idx === diagnosedIdx;
            const isDeclared = idx === declaredIdx && declaredIdx !== diagnosedIdx;
            return (
              <li key={stage} className="group relative flex flex-col items-center">
                <motion.span
                  initial={{ scale: reduced ? 1 : 0.6, opacity: reduced ? 1 : 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={{ delay: reduced ? 0 : 0.2 + idx * 0.06, duration: 0.25, ease: "easeOut" }}
                  className={[
                    "h-2.5 w-2.5 rounded-full ring-2 ring-white",
                    isDiagnosed
                      ? "bg-evidence-600 shadow-[0_0_0_3px_rgba(14,140,116,0.2)]"
                      : reached
                        ? "bg-evidence-400"
                        : "border border-navy-200 bg-white",
                    isDeclared ? "ring-2 ring-caution-400" : ""
                  ].join(" ")}
                  aria-current={isDiagnosed ? "step" : undefined}
                />
                {/* label appears on hover to keep the rail thin */}
                <span
                  className={`pointer-events-none absolute top-4 whitespace-nowrap text-[10px] leading-none opacity-0 transition-opacity group-hover:opacity-100 ${
                    isDiagnosed ? "font-semibold text-evidence-700" : "text-ink-500"
                  }`}
                >
                  {label("stage", stage)}
                </span>
              </li>
            );
          })}
        </ol>
      </div>
    </div>
  );
}

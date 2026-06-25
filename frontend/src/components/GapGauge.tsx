import { STAGE_ORDER, gapTone, stageIndex } from "../lib/diagnosis";
import { useCountUp, useInViewOnce } from "../lib/motion";
import { useI18n } from "../i18n/useI18n";

const TONE_FILL: Record<string, string> = {
  evidence: "bg-evidence-400",
  caution: "bg-caution-400",
  flag: "bg-flag-600"
};
const TONE_DOT: Record<string, string> = {
  evidence: "bg-evidence-600 ring-evidence-100",
  caution: "bg-caution-600 ring-caution-100",
  flag: "bg-flag-600 ring-flag-100"
};

/**
 * The signature perception–reality visualizer. A hollow "declared" marker and a
 * solid "evidenced" marker sit on the S1→S6 rail; on view the evidenced marker
 * travels from the declared position to the real one, and the span between them
 * fills with the gap-magnitude tone (red only for real divergence).
 * Uses logical inset properties so it mirrors correctly in RTL.
 */
export function GapGauge({
  declaredStage,
  diagnosedStage,
  gapLevel,
  confidence,
  provisional,
  bare = false
}: {
  declaredStage: string;
  diagnosedStage: string;
  gapLevel: string;
  confidence: number;
  provisional?: boolean;
  /** Drop the navy panel wrapper to embed inside the cinematic hero. */
  bare?: boolean;
}) {
  const { t, label } = useI18n();
  const { ref, inView } = useInViewOnce<HTMLDivElement>();

  const n = STAGE_ORDER.length;
  const declaredIdx = Math.max(0, stageIndex(declaredStage));
  const evidencedIdx = Math.max(0, stageIndex(diagnosedStage));
  const declaredPct = (declaredIdx / (n - 1)) * 100;
  const evidencedPct = (evidencedIdx / (n - 1)) * 100;

  const progress = useCountUp(1, inView, 900);
  const currentEvidPct = declaredPct + (evidencedPct - declaredPct) * progress;
  const fillStart = Math.min(declaredPct, currentEvidPct);
  const fillWidth = Math.abs(currentEvidPct - declaredPct);

  const tone = gapTone(gapLevel);
  const hasGap = declaredIdx !== evidencedIdx;

  return (
    <div ref={ref} className={bare ? "relative" : "panel-navy p-6"}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="overline text-navy-200">{t("gap.title")}</p>
          <p className="mt-2 max-w-xl text-lg font-semibold leading-snug text-white">
            {hasGap ? (
              <>
                {t("gap.declared")} <span className="text-navy-200">{label("stage", declaredStage)}</span>. {t("gap.evidenced")}{" "}
                <span className={tone === "flag" ? "text-flag-400" : "text-evidence-400"}>{label("stage", diagnosedStage)}</span>.
              </>
            ) : (
              t("gap.none")
            )}
          </p>
        </div>
        <div className="text-end">
          <span className={`chip ${tone === "flag" ? "bg-flag-600 text-white" : tone === "caution" ? "bg-caution-600 text-white" : "bg-evidence-600 text-white"}`}>
            {t("gap.level", { gap: label("gap", gapLevel) })}
          </span>
          <p className="mt-2 text-xs text-navy-200">
            {provisional
              ? t("gap.confidenceProvisional", { percent: Math.round(confidence * 100) })
              : t("confidence.label", { percent: Math.round(confidence * 100) })}
          </p>
        </div>
      </div>

      {/* The rail */}
      <div className="mt-8 mb-2">
        <div className="relative h-1.5 rounded-full bg-white/15">
          {/* gap-magnitude fill */}
          <div
            className={`absolute h-full rounded-full ${TONE_FILL[tone]}`}
            style={{ insetInlineStart: `${fillStart}%`, width: `${fillWidth}%` }}
          />
          {/* stage ticks */}
          {STAGE_ORDER.map((stage, idx) => (
            <span
              key={stage}
              className="absolute top-1/2 h-2 w-2 -translate-y-1/2 rounded-full bg-white/30"
              style={{ insetInlineStart: `${(idx / (n - 1)) * 100}%`, marginInlineStart: "-4px" }}
            />
          ))}
          {/* declared marker (hollow) */}
          <span
            className="absolute top-1/2 z-10 h-4 w-4 -translate-y-1/2 rounded-full border-2 border-navy-200 bg-navy-900"
            style={{ insetInlineStart: `${declaredPct}%`, marginInlineStart: "-8px" }}
            aria-label={`${t("gap.declared")} ${label("stage", declaredStage)}`}
          />
          {/* evidenced marker (solid, animated) */}
          <span
            className={`absolute top-1/2 z-20 h-5 w-5 -translate-y-1/2 rounded-full ring-4 ${TONE_DOT[tone]} ${provisional ? "border-2 border-dashed border-white" : ""}`}
            style={{ insetInlineStart: `${currentEvidPct}%`, marginInlineStart: "-10px" }}
            aria-label={`${t("gap.evidenced")} ${label("stage", diagnosedStage)}`}
          />
        </div>
        {/* stage labels */}
        <div className="mt-3 flex justify-between">
          {STAGE_ORDER.map((stage, idx) => {
            const isDeclared = idx === declaredIdx;
            const isEvidenced = idx === evidencedIdx;
            return (
              <span
                key={stage}
                className={`w-0 flex-1 text-center text-[10px] leading-tight ${
                  isEvidenced ? "font-semibold text-white" : isDeclared ? "font-medium text-navy-200" : "text-navy-200/60"
                }`}
              >
                {label("stage", stage)}
              </span>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/** Compact stage rail for reuse (e.g. journey milestones); its fill animates in on view. */
export function StageTrack({ currentStage }: { currentStage: string }) {
  const { label } = useI18n();
  const { ref, inView } = useInViewOnce<HTMLDivElement>();
  const n = STAGE_ORDER.length;
  const currentIdx = Math.max(0, stageIndex(currentStage));
  const target = (currentIdx / (n - 1)) * 100;
  const pct = useCountUp(target, inView, 900);
  return (
    <div ref={ref}>
      <div className="relative h-1.5 rounded-full bg-navy-100">
        <div className="absolute h-full rounded-full bg-evidence-600" style={{ insetInlineStart: 0, width: `${pct}%` }} />
        <span
          className="absolute top-1/2 h-4 w-4 -translate-y-1/2 rounded-full bg-evidence-600 ring-4 ring-evidence-100"
          style={{ insetInlineStart: `${pct}%`, marginInlineStart: "-8px" }}
        />
      </div>
      <div className="mt-2 flex justify-between">
        {STAGE_ORDER.map((stage, idx) => (
          <span key={stage} className={`w-0 flex-1 text-center text-[10px] ${idx === currentIdx ? "font-semibold text-navy-700" : "text-ink-400"}`}>
            {label("stage", stage)}
          </span>
        ))}
      </div>
    </div>
  );
}

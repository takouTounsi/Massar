import { motion, useReducedMotion } from "framer-motion";
import { useCountUp, useInViewOnce } from "../lib/motion";

type Tone = "evidence" | "caution" | "flag" | "gold" | "navy";

const STROKE: Record<Tone, string> = {
  evidence: "var(--evidence-600)",
  caution: "var(--caution-600)",
  flag: "var(--flag-600)",
  gold: "#C8961C",
  navy: "var(--navy-600)"
};

/**
 * SVG progress ring. The filled arc draws itself on view (stroke-dashoffset)
 * and the centre value counts up. Reduced-motion snaps to the final state.
 */
export function ConfidenceRing({
  value,
  size = 120,
  strokeWidth = 9,
  tone = "evidence",
  suffix = "",
  caption,
  decimals = 0
}: {
  /** 0–100 */
  value: number;
  size?: number;
  strokeWidth?: number;
  tone?: Tone;
  suffix?: string;
  caption?: string;
  decimals?: number;
}) {
  const reduced = useReducedMotion() ?? false;
  const { ref, inView } = useInViewOnce<HTMLDivElement>();
  const clamped = Math.max(0, Math.min(100, value));
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const active = inView || reduced;
  const animated = useCountUp(clamped, active, 900);
  const display = decimals > 0 ? animated.toFixed(decimals) : Math.round(animated);
  const offset = circumference * (1 - clamped / 100);

  return (
    <div ref={ref} className="relative inline-grid place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90" aria-hidden>
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="var(--navy-100)" strokeWidth={strokeWidth} />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={STROKE[tone]}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: reduced ? offset : circumference }}
          animate={{ strokeDashoffset: active ? offset : circumference }}
          transition={{ duration: 0.9, ease: "easeOut" }}
        />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center leading-none">
        <div>
          <p className="text-2xl font-semibold tabular-nums text-ink-900">
            {display}
            {suffix ? <span className="text-base">{suffix}</span> : null}
          </p>
          {caption ? <p className="mt-1 text-[10px] font-medium uppercase tracking-wide text-ink-500">{caption}</p> : null}
        </div>
      </div>
    </div>
  );
}

import { Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useI18n } from "../i18n/useI18n";

type ArchetypeData = {
  label: string;
  archetype_id: string;
  confidence: number;
  pattern_description: string;
  strategic_recommendation: string;
  next_stage_gate: string;
  triggering_signals?: Array<{ description: string; evidence: string }>;
};

/**
 * Ambient particle field — small, slow-drifting dots behind the archetype
 * copy. Pure CSS keyframes (no canvas, no library) since this section is
 * decorative atmosphere, not data. Respects reduced-motion via the
 * `motion-reduce:` Tailwind variant on each dot.
 */
function ArchetypeParticles() {
  const dots = useRef(
    Array.from({ length: 22 }, (_, i) => ({
      id: i,
      left: Math.round(Math.random() * 100),
      top: Math.round(Math.random() * 100),
      duration: 8 + Math.random() * 12,
      delay: Math.random() * 6,
      size: 1.5 + Math.random() * 1.5
    }))
  ).current;

  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
      {dots.map((dot) => (
        <span
          key={dot.id}
          className="absolute rounded-full bg-white/25 motion-reduce:animate-none"
          style={{
            left: `${dot.left}%`,
            top: `${dot.top}%`,
            width: dot.size,
            height: dot.size,
            animation: `archetype-drift ${dot.duration}s ease-in-out ${dot.delay}s infinite`
          }}
        />
      ))}
      <style>{`
        @keyframes archetype-drift {
          0%, 100% { transform: translateY(0); opacity: 0.15; }
          50% { transform: translateY(-22px); opacity: 0.4; }
        }
      `}</style>
    </div>
  );
}

/**
 * Founder-archetype hero. When real archetype data is available (from the
 * intelligence service) it renders the full narrative; otherwise it shows an
 * honest, action-oriented empty state rather than inventing a pattern. The
 * deterministic/LLM distinction matters here — this section's prose is the
 * one place in the report that is narrative rather than computed, so the
 * empty state is explicit about that instead of guessing.
 */
export function ArchetypeHero({ data }: { data: ArchetypeData | null }) {
  const { t } = useI18n();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  if (!data) {
    return (
      <div className="hero-cinematic relative flex min-h-[220px] flex-col justify-center overflow-hidden p-6 sm:p-8">
        <ArchetypeParticles />
        <div className="relative z-10 max-w-xl">
          <p className="text-overline text-navy-200">{t("archetype.eyebrow")}</p>
          <h3 className="mt-2 text-2xl font-medium text-white">{t("archetype.emptyTitle")}</h3>
          <p className="mt-2 text-sm leading-relaxed text-navy-200">{t("archetype.emptyBody")}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="hero-cinematic relative min-h-[280px] overflow-hidden p-6 sm:p-8">
      <ArchetypeParticles />
      <div className="relative z-10 grid gap-6 lg:grid-cols-[1.6fr_1fr]">
        <div className={mounted ? "animate-rise" : "opacity-0"}>
          <p className="inline-flex items-center gap-1.5 text-overline text-navy-200">
            <Sparkles size={12} className="text-gold-300" /> {t("archetype.eyebrow")} · {Math.round(data.confidence * 100)}% {t("archetype.confidence")}
          </p>
          <h3 className="mt-2 text-3xl font-medium text-white">{data.label}</h3>
          <p className="mt-3 max-w-xl text-sm leading-relaxed text-white/70">{data.pattern_description}</p>

          {data.triggering_signals?.length ? (
            <div className="mt-4 flex flex-wrap gap-1.5">
              {data.triggering_signals.slice(0, 3).map((sig, idx) => (
                <span key={idx} className="chip border border-caution-400/30 bg-white/10 text-[11px] text-caution-200">
                  {sig.description} · {sig.evidence}
                </span>
              ))}
            </div>
          ) : null}

          <p className="mt-4 text-sm font-medium text-gold-300">
            {t("archetype.nextGate")}: {data.next_stage_gate}
          </p>
        </div>
        <div className="flex flex-col justify-center gap-3 border-t border-white/10 pt-4 lg:border-t-0 lg:border-s lg:ps-6 lg:pt-0">
          <p className="text-overline text-navy-200">{t("archetype.recommendation")}</p>
          <p className="text-sm leading-relaxed text-white/80">{data.strategic_recommendation}</p>
        </div>
      </div>
    </div>
  );
}
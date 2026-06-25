import { Activity, Crosshair, ShieldQuestion, Target } from "lucide-react";
import type { ReactNode } from "react";
import type { DashboardAnalysis } from "../api/types";
import { PROVISIONAL_CONFIDENCE, orderedScores, weakestScore } from "../lib/diagnosis";
import { useCountUp, useInViewOnce } from "../lib/motion";
import { useI18n } from "../i18n/useI18n";
import { GapGauge } from "./GapGauge";
import { Particles } from "./Particles";

function CommandStat({
  icon,
  label,
  value,
  suffix,
  active,
  tone = "white"
}: {
  icon: ReactNode;
  label: string;
  value: number;
  suffix?: string;
  active: boolean;
  tone?: "white" | "flag" | "gold" | "evidence";
}) {
  const animated = useCountUp(value, active, 900);
  const toneClass =
    tone === "flag" ? "text-flag-400" : tone === "gold" ? "text-gold-300" : tone === "evidence" ? "text-evidence-400" : "text-white";
  return (
    <div className="flex items-center gap-2.5 rounded-xl border border-white/10 bg-white/5 px-3 py-2 backdrop-blur">
      <span className="text-navy-200">{icon}</span>
      <div className="leading-tight">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-navy-200">{label}</p>
        <p className={`text-lg font-bold tabular-nums ${toneClass}`}>
          {Math.round(animated)}
          {suffix ? <span className="text-xs font-semibold">{suffix}</span> : null}
        </p>
      </div>
    </div>
  );
}

/** Cinematic mission-control hero: drifting particles, the animated gap gauge, and a live command-stat strip. */
export function MissionHero({ analysis, provisional }: { analysis: DashboardAnalysis; provisional: boolean }) {
  const { t, label } = useI18n();
  const { ref, inView } = useInViewOnce<HTMLDivElement>();
  const weakest = weakestScore(analysis.scores);
  const weakestValue = weakest ? Math.round(analysis.scores[weakest]) : 0;
  const stageBlocking = analysis.blockers.filter((b) => b.stage_blocking).length;

  return (
    <section ref={ref} className="hero-cinematic p-6 sm:p-8">
      <Particles className="pointer-events-none absolute inset-0 h-full w-full opacity-70" />
      <div className="relative">
        <p className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1 text-overline font-semibold uppercase text-navy-200">
          <Activity size={12} className="text-evidence-400" /> {t("hero.missionControl")}
        </p>

        <GapGauge
          declaredStage={analysis.declared_stage}
          diagnosedStage={analysis.diagnosed_stage}
          gapLevel={analysis.gap_level}
          confidence={analysis.maturity_confidence}
          provisional={provisional}
          bare
        />

        {/* Live command strip */}
        <div className="mt-7 flex flex-wrap gap-2.5">
          <CommandStat
            icon={<ShieldQuestion size={16} />}
            label={t("hero.confidence")}
            value={Math.round(analysis.maturity_confidence * 100)}
            suffix="%"
            active={inView}
            tone={analysis.maturity_confidence < PROVISIONAL_CONFIDENCE ? "flag" : "evidence"}
          />
          <CommandStat
            icon={<Crosshair size={16} />}
            label={weakest ? label("score", weakest) : t("scores.weakestLink")}
            value={weakestValue}
            suffix="/100"
            active={inView}
            tone="flag"
          />
          <CommandStat icon={<Target size={16} />} label={t("hero.stageBlockers")} value={stageBlocking} active={inView} tone="flag" />
          <CommandStat icon={<Activity size={16} />} label={t("progress.global")} value={Math.round(analysis.progress)} suffix="%" active={inView} tone="gold" />
        </div>
      </div>
    </section>
  );
}

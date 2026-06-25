import { motion } from "framer-motion";
import { Check, ChevronRight, Lock, Sparkles, Zap } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { GeneratedRoadmapAction } from "../api/types";
import { unlockPulse } from "../lib/anim";
import { useI18n } from "../i18n/useI18n";
import { CitationChip } from "./CitationChip";
import { CounterfactualHover } from "./CounterfactualHover";
import { ParticleBurst } from "./ParticleBurst";

const HORIZON_ORDER = ["IMMEDIATE", "SHORT_TERM", "MEDIUM_TERM", "LONG_TERM"];

type NodeState = "completed" | "available" | "locked";

function nodeState(action: GeneratedRoadmapAction, completedIds: Set<string>): NodeState {
  if (action.status === "COMPLETED" || action.status === "DONE") return "completed";
  const unmet = action.depends_on.filter((dep) => !completedIds.has(dep));
  return unmet.length > 0 ? "locked" : "available";
}

function TreeNode({
  action,
  state,
  open,
  onToggle,
  onStatusChange,
  isUpdating,
  justUnlocked,
  scores
}: {
  action: GeneratedRoadmapAction;
  state: NodeState;
  open: boolean;
  onToggle: () => void;
  onStatusChange: (status: string) => void;
  isUpdating?: boolean;
  justUnlocked?: boolean;
  scores?: Record<string, number>;
}) {
  const { t, label, text } = useI18n();
  const [hover, setHover] = useState(false);

  const shell =
    state === "completed"
      ? "badge-collected shadow-glow-gold"
      : state === "available"
        ? "border-navy-300 bg-white shadow-glow-navy hover:-translate-y-0.5"
        : "node-locked";

  const Icon = state === "completed" ? Check : state === "available" ? Zap : Lock;
  const iconWrap =
    state === "completed" ? "bg-gold-400 text-white" : state === "available" ? "bg-navy-700 text-white" : "bg-white/70 text-ink-400";

  return (
    <motion.div
      className={`relative animate-unlock rounded-card border-2 p-3.5 transition duration-300 ease-sovereign ${shell}`}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      {...(justUnlocked ? unlockPulse : {})}
    >
      {justUnlocked ? <ParticleBurst /> : null}
      {state === "available" && scores ? (
        <CounterfactualHover open={hover && !open} scores={scores} improvesScores={action.improves_scores} estimatedEffort={action.estimated_effort} />
      ) : null}
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        disabled={state === "locked"}
        className="flex w-full items-start gap-3 text-start focus-visible:outline-none disabled:cursor-not-allowed"
      >
        <span className={`mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg ${iconWrap} ${state === "available" ? "animate-pulse-glow" : ""}`}>
          <Icon size={16} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-2">
            <span className="text-[10px] font-bold uppercase tracking-wide text-ink-400">
              {state === "completed" ? t("roadmap.completedNode") : state === "available" ? t("roadmap.unlocked") : t("roadmap.locked")}
            </span>
            {action.improves_scores.slice(0, 1).map((score) => (
              <span key={score} className="chip bg-navy-50 text-[10px] text-navy-700">+{label("score", score)}</span>
            ))}
          </span>
          <span className="mt-0.5 block truncate text-sm font-semibold text-ink-900">{text(action.title)}</span>
        </span>
        {state !== "locked" ? <ChevronRight size={16} className={`mt-1.5 shrink-0 text-ink-400 transition-transform duration-300 ${open ? "rotate-90" : ""}`} /> : null}
      </button>

      {open && state !== "locked" ? (
        <div className="animate-rise mt-3 space-y-2.5 border-t border-navy-100 pt-3">
          <p className="text-sm text-ink-600">{text(action.description)}</p>
          {(action.source_urls.length > 0 || action.resource_ids.length > 0) && (
            <div className="flex flex-wrap gap-1.5">
              {action.source_urls.map((url) => (
                <CitationChip key={url} url={url} />
              ))}
            </div>
          )}
          {state === "available" ? (
            <div className="flex flex-wrap gap-2">
              <button className="btn btn-secondary" disabled={isUpdating || action.status === "IN_PROGRESS"} onClick={() => onStatusChange("IN_PROGRESS")}>
                {t("common.inProgress")}
              </button>
              <button className="btn btn-primary" disabled={isUpdating} onClick={() => onStatusChange("COMPLETED")}>
                <Sparkles size={15} /> {t("roadmap.unlock")}
              </button>
            </div>
          ) : (
            <span className="inline-flex items-center gap-2 rounded-lg bg-gold-50 px-3 py-1.5 text-sm font-semibold text-gold-600">
              <Check size={15} /> {t("common.actionCompleted")}
            </span>
          )}
        </div>
      ) : null}
    </motion.div>
  );
}

/** The roadmap as a tiered unlock tree: mastered (gold), available frontier (glowing navy), locked (frosted). */
export function RoadmapTree({
  actions,
  onStatusChange,
  isUpdating,
  scores
}: {
  actions: GeneratedRoadmapAction[];
  onStatusChange: (actionId: string, status: string) => void;
  isUpdating?: boolean;
  scores?: Record<string, number>;
}) {
  const { t, label } = useI18n();
  const [openId, setOpenId] = useState<string | null>(null);
  const completedIds = new Set(actions.filter((a) => a.status === "COMPLETED" || a.status === "DONE").map((a) => a.id));

  // Detect nodes that crossed locked → available since the last render so we can
  // play the unlock beat exactly once (skipped on first mount).
  const availableIds = actions.filter((a) => nodeState(a, completedIds) === "available").map((a) => a.id);
  const prevAvailable = useRef<Set<string> | null>(null);
  const [justUnlocked, setJustUnlocked] = useState<Set<string>>(new Set());
  useEffect(() => {
    const current = new Set(availableIds);
    if (prevAvailable.current) {
      const fresh = [...current].filter((id) => !prevAvailable.current!.has(id));
      if (fresh.length > 0) {
        setJustUnlocked(new Set(fresh));
        const timer = window.setTimeout(() => setJustUnlocked(new Set()), 900);
        prevAvailable.current = current;
        return () => window.clearTimeout(timer);
      }
    }
    prevAvailable.current = current;
  }, [availableIds.join(",")]);

  const tiers = HORIZON_ORDER.map((horizon) => ({
    horizon,
    items: actions.filter((a) => a.horizon === horizon)
  })).filter((tier) => tier.items.length > 0);
  // any horizons not in the known order
  const known = new Set(HORIZON_ORDER);
  const extra = actions.filter((a) => !known.has(a.horizon));
  if (extra.length > 0) tiers.push({ horizon: "OTHER", items: extra });

  return (
    <div className="space-y-5">
      {tiers.map((tier, tierIdx) => (
        <div key={tier.horizon} className="relative">
          {tierIdx < tiers.length - 1 ? <span aria-hidden className="absolute bottom-0 start-3 top-9 w-px bg-navy-100" /> : null}
          <div className="mb-2.5 flex items-center gap-2">
            <span className="grid h-6 w-6 place-items-center rounded-full bg-navy-700 text-[11px] font-bold text-white">{tierIdx + 1}</span>
            <h3 className="text-sm font-semibold text-ink-900">{label("horizon", tier.horizon)}</h3>
          </div>
          <div className="grid gap-2.5 ps-9 md:grid-cols-2">
            {tier.items.map((action) => (
              <TreeNode
                key={action.id}
                action={action}
                state={nodeState(action, completedIds)}
                open={openId === action.id}
                onToggle={() => setOpenId((cur) => (cur === action.id ? null : action.id))}
                onStatusChange={(status) => onStatusChange(action.id, status)}
                isUpdating={isUpdating}
                justUnlocked={justUnlocked.has(action.id)}
                scores={scores}
              />
            ))}
          </div>
        </div>
      ))}
      <p className="ps-9 text-xs text-ink-400">{t("roadmap.treeSubtitle")}</p>
    </div>
  );
}

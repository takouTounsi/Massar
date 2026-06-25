import { Award, Bookmark, BookmarkCheck } from "lucide-react";
import type { Resource } from "../api/types";
import { useSavedResources } from "../lib/collection";
import { useI18n } from "../i18n/useI18n";
import { CitationChip } from "./CitationChip";
import { EligibilityBadge } from "./EligibilityBadge";

/** Relevance heuristic (0–100) from match strength + eligibility, until the
 *  engine's similarity_score is wired. Labelled as relevance in the UI. */
function relevanceOf(resource: Resource): number {
  const bonus = resource.eligibility_status === "ELIGIBLE" ? 25 : resource.eligibility_status === "POSSIBLY_ELIGIBLE" ? 10 : 0;
  return Math.min(100, 40 + resource.matched_reasons.length * 15 + bonus);
}

/** A collectible program "badge": hovers rise, gold-rims and shimmers when saved. */
export function ResourceCard({ resource }: { resource: Resource }) {
  const { t, text } = useI18n();
  const { saved, toggleSaved } = useSavedResources();
  const isSaved = saved.has(resource.resource_id);
  const relevance = relevanceOf(resource);

  return (
    <article
      className={`group relative overflow-hidden rounded-card border-2 p-4 transition duration-300 ease-sovereign hover:-translate-y-1 ${
        isSaved ? "badge-collected shadow-glow-gold" : "border-navy-100 bg-white shadow-trust hover:border-gold-300 hover:shadow-glow-gold"
      }`}
    >
      {/* gold shimmer sweep on collected badges */}
      {isSaved ? <span aria-hidden className="gold-shimmer pointer-events-none absolute inset-0 animate-shimmer" /> : null}

      <div className="relative flex items-start justify-between gap-3">
        <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-xl ${isSaved ? "bg-gold-400 text-white" : "bg-navy-50 text-navy-600 group-hover:bg-gold-100 group-hover:text-gold-600"}`}>
          <Award size={18} />
        </span>
        <EligibilityBadge status={resource.eligibility_status} />
      </div>

      <h3 className="relative mt-3 font-semibold text-ink-900">{resource.name}</h3>
      <p className="relative text-sm text-ink-500">{resource.institution}</p>
      <p className="relative mt-2 text-sm text-ink-700">{resource.matched_reasons.map(text).join(" · ")}</p>

      {/* relevance indicator */}
      <div className="relative mt-3">
        <div className="flex items-center justify-between text-[11px] text-ink-400">
          <span>{t("resources.relevance")}</span>
          <span className="tabular-nums">{relevance}%</span>
        </div>
        <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-navy-100">
          <div className="h-full rounded-full bg-gold-400" style={{ width: `${relevance}%` }} />
        </div>
      </div>

      <div className="relative mt-3 flex items-center justify-between gap-2">
        <CitationChip url={resource.source_url} label={resource.institution} />
        <button
          type="button"
          onClick={() => toggleSaved(resource.resource_id)}
          aria-pressed={isSaved}
          className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold-400 ${
            isSaved ? "bg-gold-400 text-white" : "border border-navy-200 text-navy-700 hover:border-gold-400 hover:text-gold-600"
          }`}
        >
          {isSaved ? <BookmarkCheck size={14} /> : <Bookmark size={14} />}
          {isSaved ? t("resources.saved") : t("resources.save")}
        </button>
      </div>
    </article>
  );
}

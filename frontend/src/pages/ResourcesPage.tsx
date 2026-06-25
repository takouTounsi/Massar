import { Award } from "lucide-react";
import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingState } from "../components/LoadingState";
import { ResourceCard } from "../components/ResourceCard";
import { useResources } from "../hooks/useResources";
import { useSavedResources } from "../lib/collection";
import { useI18n } from "../i18n/useI18n";

const SAVED_FILTER = "__saved__";

export function ResourcesPage() {
  const { projectId = "" } = useParams();
  const resourcesQuery = useResources(projectId);
  const { saved } = useSavedResources();
  const { t, text } = useI18n();
  const [filter, setFilter] = useState<string>("all");

  const resources = useMemo(() => resourcesQuery.data ?? [], [resourcesQuery.data]);
  const categories = useMemo(() => Array.from(new Set(resources.map((r) => r.category).filter(Boolean))), [resources]);

  if (resourcesQuery.isLoading) return <LoadingState />;
  if (resourcesQuery.isError) return <ErrorState message={t("resources.loadError")} onRetry={() => resourcesQuery.refetch()} />;
  if (resources.length === 0) return <EmptyState title={t("resources.empty")} />;

  const collected = resources.filter((r) => saved.has(r.resource_id)).length;
  const filtered = resources.filter((r) => {
    if (filter === "all") return true;
    if (filter === SAVED_FILTER) return saved.has(r.resource_id);
    return r.category === filter;
  });

  const pills = [
    { key: "all", text: t("resources.filterAll") },
    ...categories.map((c) => ({ key: c, text: text(c) })),
    { key: SAVED_FILTER, text: `${t("resources.savedTab")} (${collected})` }
  ];

  return (
    <section className="grid gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold text-ink-900">{t("resources.title")}</h2>
          <p className="text-sm text-ink-500">{t("resources.subtitle")}</p>
        </div>
        <span className="inline-flex items-center gap-2 rounded-lg border border-gold-300 bg-gold-50 px-3 py-1.5 text-sm font-semibold text-gold-600">
          <Award size={16} /> {t("resources.collected", { count: collected })}
        </span>
      </div>

      {/* filter pills */}
      <div className="flex flex-wrap gap-2 overflow-x-auto">
        {pills.map((pill) => {
          const active = filter === pill.key;
          return (
            <button
              key={pill.key}
              type="button"
              onClick={() => setFilter(pill.key)}
              aria-pressed={active}
              className={`chip whitespace-nowrap transition ${active ? "bg-navy-800 text-white" : "bg-navy-50 text-ink-500 hover:bg-navy-100"}`}
            >
              {pill.text}
            </button>
          );
        })}
      </div>

      {filtered.length > 0 ? (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map((resource) => (
            <ResourceCard resource={resource} key={resource.resource_id} />
          ))}
        </div>
      ) : (
        <EmptyState title={t("resources.empty")} />
      )}
    </section>
  );
}

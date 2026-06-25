import { useI18n } from "../i18n/useI18n";

export function LoadingState({ label }: { label?: string }) {
  const { t } = useI18n();
  const resolvedLabel = label ?? t("common.loading");

  return (
    <div className="panel animate-pulse p-5">
      <div className="mb-3 h-4 w-40 rounded bg-navy-100" />
      <div className="grid gap-2">
        <div className="h-3 rounded bg-navy-50" />
        <div className="h-3 w-2/3 rounded bg-navy-50" />
      </div>
      <p className="sr-only">{resolvedLabel}</p>
    </div>
  );
}
import { useI18n } from "../i18n/useI18n";

export function ProgressSummary({ value }: { value: number }) {
  const { t } = useI18n();

  return (
    <div className="panel p-5">
      <div className="flex items-center justify-between">
        <div>
          <p className="overline">{t("progress.global")}</p>
          <p className="mt-2 text-2xl font-semibold text-ink-900">{Math.round(value)}%</p>
        </div>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-navy-100">
        <div className="h-full rounded-full bg-evidence-600 transition-[width] duration-700 ease-sovereign" style={{ width: `${Math.max(4, Math.min(value, 100))}%` }} />
      </div>
    </div>
  );
}
import { RefreshCw } from "lucide-react";
import { useI18n } from "../i18n/useI18n";

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const { t } = useI18n();

  return (
    <div className="panel border-flag-200 bg-flag-50 p-5 text-flag-800">
      <p className="font-semibold">{t("common.errorTitle")}</p>
      <p className="mt-1 text-sm">{message}</p>
      {onRetry ? (
        <button className="btn btn-secondary mt-4" onClick={onRetry}>
          <RefreshCw size={16} /> {t("common.retry")}
        </button>
      ) : null}
    </div>
  );
}
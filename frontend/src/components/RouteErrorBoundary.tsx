import { AlertTriangle, RefreshCw } from "lucide-react";
import { isRouteErrorResponse, useNavigate, useRouteError } from "react-router-dom";
import { useI18n } from "../i18n/useI18n";

/**
 * Route-level errorElement: any uncaught render error (e.g. a future null field
 * read on a fresh project) is contained here instead of taking down the whole
 * app with the raw React error screen.
 */
export function RouteErrorBoundary() {
  const error = useRouteError();
  const navigate = useNavigate();
  const { t } = useI18n();

  const detail = isRouteErrorResponse(error)
    ? `${error.status} ${error.statusText}`
    : error instanceof Error
    ? error.message
    : t("error.unexpected");

  return (
    <main className="grid min-h-screen place-items-center bg-paper px-4">
      <div className="panel grid max-w-md place-items-center p-8 text-center">
        <span className="mb-3 grid h-12 w-12 place-items-center rounded-full bg-flag-50 text-flag-600">
          <AlertTriangle size={24} />
        </span>
        <h1 className="text-lg font-semibold text-ink-900">{t("error.title")}</h1>
        <p className="mt-1 max-w-sm text-sm text-ink-500">{t("error.body")}</p>
        <p className="mt-2 max-w-sm break-words text-xs text-ink-400">{detail}</p>
        <div className="mt-5 flex gap-2">
          <button className="btn btn-secondary" onClick={() => navigate(0)}>
            <RefreshCw size={16} /> {t("common.retry")}
          </button>
          <button className="btn btn-primary" onClick={() => navigate("/dashboard")}>
            {t("error.backHome")}
          </button>
        </div>
      </div>
    </main>
  );
}

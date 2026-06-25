import { ClipboardList, Play } from "lucide-react";
import { Link } from "react-router-dom";
import { useI18n } from "../i18n/useI18n";

/**
 * Shown when a project exists but has no diagnosis yet (intake not run). Every
 * dashboard surface reads off `analysis`, which is null on a fresh project — so
 * each page guards on it and renders this CTA instead of a half-built view.
 */
export function NoDiagnosisState({ projectId }: { projectId: string }) {
  const { t } = useI18n();

  return (
    <div className="panel grid place-items-center p-10 text-center">
      <span className="mb-4 grid h-14 w-14 place-items-center rounded-full bg-navy-50 text-navy-600">
        <ClipboardList size={26} />
      </span>
      <h3 className="text-lg font-semibold text-ink-900">{t("diagnosis.emptyTitle")}</h3>
      <p className="mt-1 max-w-md text-sm text-ink-500">{t("diagnosis.emptyBody")}</p>
      <Link className="btn btn-primary mt-5" to={`/projects/${projectId}/intake`}>
        <Play size={16} /> {t("diagnosis.startIntake")}
      </Link>
    </div>
  );
}

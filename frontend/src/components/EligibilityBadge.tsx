import { useI18n } from "../i18n/useI18n";

export function EligibilityBadge({ status }: { status: string }) {
  const { label } = useI18n();
  const tone =
    status === "ELIGIBLE"
      ? "bg-evidence-50 text-evidence-700"
      : status === "POSSIBLY_ELIGIBLE"
        ? "bg-caution-50 text-caution-700"
        : "bg-navy-50 text-navy-700";
  return <span className={`chip ${tone}`}>{label("eligibility", status)}</span>;
}
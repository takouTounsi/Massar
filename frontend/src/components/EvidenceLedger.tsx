import { Info } from "lucide-react";
import type { DashboardAnalysis } from "../api/types";
import { orderedBlockers } from "../lib/diagnosis";
import { useI18n } from "../i18n/useI18n";

type LedgerStatus = "OBSERVED" | "CONFIRMED" | "UNVERIFIED" | "CONTRADICTED" | "MISSING";

const STATUS_DOT: Record<LedgerStatus, string> = {
  OBSERVED: "bg-navy-500",
  CONFIRMED: "bg-evidence-600",
  UNVERIFIED: "bg-caution-600",
  CONTRADICTED: "bg-flag-600",
  MISSING: "bg-ink-400"
};

export function EvidenceLedgerRow({ text, status }: { text: string; status: LedgerStatus }) {
  const { label } = useI18n();
  return (
    <div className="flex items-center justify-between gap-3 py-2">
      <span className="flex items-center gap-2.5 text-sm text-ink-700">
        <span className={`h-2 w-2 shrink-0 rounded-full ${STATUS_DOT[status]}`} />
        {text}
      </span>
      <span className="overline shrink-0">{label("ledgerStatus", status)}</span>
    </div>
  );
}

/**
 * The evidence ledger for the diagnosis. Observed signals come from blocker
 * evidence (real strings); MISSING rows come from analysis.missing_fields.
 * The full four-status ledger (CONFIRMED/UNVERIFIED/CONTRADICTED) lives in the
 * intake engine and is not exposed on the dashboard payload — flagged below.
 */
export function EvidenceLedger({ analysis }: { analysis: DashboardAnalysis }) {
  const { t, label, text } = useI18n();
  const blockers = orderedBlockers(analysis.blockers);
  const missing = analysis.missing_fields ?? [];

  if (blockers.length === 0 && missing.length === 0) return null;

  return (
    <div className="panel p-5">
      <h3 className="font-semibold text-ink-900">{t("evidence.title")}</h3>
      <div className="mt-2 divide-y divide-navy-100">
        {blockers.flatMap((blocker) =>
          blocker.evidence.map((item, idx) => (
            <EvidenceLedgerRow key={`${blocker.id}-${idx}`} text={text(item)} status={blocker.stage_blocking ? "CONTRADICTED" : "OBSERVED"} />
          ))
        )}
        {missing.map((field) => (
          <EvidenceLedgerRow key={field} text={label("field", field)} status="MISSING" />
        ))}
      </div>
      <p className="mt-3 flex items-start gap-1.5 text-xs text-ink-400">
        <Info size={13} className="mt-0.5 shrink-0" />
        {t("evidence.statusNote")}
      </p>
    </div>
  );
}

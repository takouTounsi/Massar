import { useI18n } from "../i18n/useI18n";

type BoardSummaryData = {
  executive_summary: string;
  key_risk: string;
  main_opportunity: string;
  strategic_focus: string;
  generated_by?: string;
};

/** Investor/board-memo summary: four plain-prose cells, the colored left
 * border is the only decoration — McKinsey-memo register, no filler. */
export function BoardSummaryGrid({ data }: { data: BoardSummaryData | null }) {
  const { t } = useI18n();

  const cells: Array<{ label: string; value: string; border: string }> = [
    { label: t("board.executiveSummary"), value: data?.executive_summary ?? t("board.empty"), border: "border-s-evidence-500" },
    { label: t("board.keyRisk"), value: data?.key_risk ?? t("board.empty"), border: "border-s-flag-600" },
    { label: t("board.mainOpportunity"), value: data?.main_opportunity ?? t("board.empty"), border: "border-s-gold-500" },
    { label: t("board.strategicFocus"), value: data?.strategic_focus ?? t("board.empty"), border: "border-s-[#534AB7]" }
  ];

  return (
    <div className="panel p-5">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="font-semibold text-ink-900">{t("board.title")}</h3>
        {data ? null : <span className="chip bg-navy-50 text-[11px] text-ink-500">{t("swot.notGenerated")}</span>}
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {cells.map((cell) => (
          <div key={cell.label} className={`border-s-2 ${cell.border} rounded-md bg-navy-50/30 py-1 ps-3`}>
            <p className="text-overline text-ink-400">{cell.label}</p>
            <p className="mt-1 text-sm leading-relaxed text-ink-700">{cell.value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
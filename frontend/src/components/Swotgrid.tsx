import { motion } from "framer-motion";
import { Compass, ShieldAlert, Sparkles, TrendingDown } from "lucide-react";
import { bulletVariants } from "../lib/anim";
import { useI18n } from "../i18n/useI18n";

type SWOTData = {
  strengths: string[];
  weaknesses: string[];
  opportunities: string[];
  threats: string[];
  generated_by?: string;
};

type QuadrantKey = "strengths" | "weaknesses" | "opportunities" | "threats";

function QuadrantCard({
  icon: Icon,
  border,
  bg,
  titleClass,
  title,
  items
}: {
  icon: typeof Sparkles;
  border: string;
  bg: string;
  titleClass: string;
  title: string;
  items: string[];
}) {
  const { t } = useI18n();
  return (
    <div className={`rounded-card border ${border} ${bg} p-4`}>
      <p className={`flex items-center gap-1.5 text-overline ${titleClass}`}>
        <Icon size={13} /> {title}
      </p>
      {items.length > 0 ? (
        <ul className="mt-2.5 space-y-1.5">
          {items.map((item, idx) => (
            <motion.li
              key={idx}
              custom={idx}
              variants={bulletVariants}
              initial="hidden"
              animate="visible"
              className="flex gap-2 text-sm leading-snug text-ink-700"
            >
              <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-current opacity-50" />
              {item}
            </motion.li>
          ))}
        </ul>
      ) : (
        <p className="mt-2.5 text-sm text-ink-400">{t("swot.empty")}</p>
      )}
    </div>
  );
}

/** SWOT analysis as a 2x2 grid. Each quadrant degrades to a quiet empty state
 * rather than placeholder copy when the intelligence service hasn't produced
 * that list yet — never fabricate strengths/weaknesses from thin air. */
export function SWOTGrid({ data }: { data: SWOTData | null }) {
  const { t } = useI18n();
  const safe: Record<QuadrantKey, string[]> = {
    strengths: data?.strengths ?? [],
    weaknesses: data?.weaknesses ?? [],
    opportunities: data?.opportunities ?? [],
    threats: data?.threats ?? []
  };

  return (
    <div className="panel p-5">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="font-semibold text-ink-900">{t("swot.title")}</h3>
        {data ? null : <span className="chip bg-navy-50 text-[11px] text-ink-500">{t("swot.notGenerated")}</span>}
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <QuadrantCard icon={Sparkles} border="border-evidence-200" bg="bg-evidence-50/60" titleClass="text-evidence-700" title={t("swot.strengths")} items={safe.strengths} />
        <QuadrantCard icon={TrendingDown} border="border-flag-200" bg="bg-flag-50/60" titleClass="text-flag-700" title={t("swot.weaknesses")} items={safe.weaknesses} />
        <QuadrantCard icon={Compass} border="border-gold-300" bg="bg-gold-50" titleClass="text-[#8B6914]" title={t("swot.opportunities")} items={safe.opportunities} />
        <QuadrantCard icon={ShieldAlert} border="border-[#D8D4F5]" bg="bg-[#F5F3FF]" titleClass="text-[#534AB7]" title={t("swot.threats")} items={safe.threats} />
      </div>
    </div>
  );
}
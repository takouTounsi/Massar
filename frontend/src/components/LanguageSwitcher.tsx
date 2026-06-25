import { Languages } from "lucide-react";
import { languages } from "../i18n/locales";
import { useI18n } from "../i18n/useI18n";

export function LanguageSwitcher() {
  const { language, setLanguage, t } = useI18n();

  return (
    <label className="inline-flex items-center gap-2 rounded-lg border border-navy-200 bg-white px-2 py-1.5 text-sm font-medium text-navy-700">
      <Languages size={16} className="text-ink-500" />
      <span className="sr-only">{t("common.selectLanguage")}</span>
      <select
        className="bg-transparent text-sm font-medium outline-none"
        value={language}
        onChange={(event) => setLanguage(event.target.value === "ar" ? "ar" : "fr")}
        aria-label={t("common.selectLanguage")}
      >
        {languages.map((item) => (
          <option value={item.code} key={item.code}>
            {item.shortLabel}
          </option>
        ))}
      </select>
    </label>
  );
}
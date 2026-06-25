import { createContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { enumLabels, languages, messages, textLabels } from "./locales";
import type { EnumCategory, Language, MessageKey } from "./locales";

type Vars = Record<string, string | number>;

type I18nContextValue = {
  language: Language;
  setLanguage: (language: Language) => void;
  isRtl: boolean;
  dir: "ltr" | "rtl";
  t: (key: MessageKey, vars?: Vars) => string;
  label: (category: EnumCategory, value: string | undefined | null) => string;
  text: (value: string | undefined | null) => string;
};

export const I18nContext = createContext<I18nContextValue | null>(null);

const STORAGE_KEY = "massar_language";

function initialLanguage(): Language {
  if (typeof window === "undefined") return "fr";
  const stored = window.localStorage.getItem(STORAGE_KEY);
  return stored === "ar" || stored === "fr" ? stored : "fr";
}

function interpolate(template: string, vars?: Vars) {
  if (!vars) return template;
  return Object.entries(vars).reduce((current, [key, value]) => current.replace(new RegExp(`\\{${key}\\}`, "g"), String(value)), template);
}

function humanize(value: string) {
  return value.replace(/_/g, " ").toLowerCase().replace(/^./, (letter) => letter.toUpperCase());
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(initialLanguage);
  const selectedLanguage = languages.find((item) => item.code === language) ?? languages[0];
  const dir = selectedLanguage.dir;

  useEffect(() => {
    document.documentElement.lang = language;
    document.documentElement.dir = dir;
    window.localStorage.setItem(STORAGE_KEY, language);
  }, [dir, language]);

  const value = useMemo<I18nContextValue>(() => {
    return {
      language,
      setLanguage: setLanguageState,
      isRtl: dir === "rtl",
      dir,
      t: (key, vars) => interpolate(messages[language][key] ?? messages.fr[key], vars),
      label: (category, rawValue) => {
        if (!rawValue) return "";
        const current = enumLabels[language][category] as Record<string, string>;
        const fallback = enumLabels.fr[category] as Record<string, string>;
        return current[rawValue] ?? fallback[rawValue] ?? humanize(rawValue);
      },
      text: (rawValue) => {
        if (!rawValue) return "";
        const current = textLabels[language] as Record<string, string>;
        const fallback = textLabels.fr as Record<string, string>;
        return current[rawValue] ?? fallback[rawValue] ?? rawValue;
      }
    };
  }, [dir, language]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}
import type { ReactNode } from "react";

export type TimelineItem = {
  id: string;
  title: string;
  subtitle?: string;
  tone?: "navy" | "evidence" | "caution" | "flag";
  icon?: ReactNode;
  current?: boolean;
};

const DOT_TONE: Record<string, string> = {
  navy: "bg-navy-700 ring-navy-100",
  evidence: "bg-evidence-600 ring-evidence-100",
  caution: "bg-caution-600 ring-caution-100",
  flag: "bg-flag-600 ring-flag-100"
};

/** Vertical milestone timeline. The rail sits on the inline-start edge so it mirrors in RTL. */
export function Timeline({ items }: { items: TimelineItem[] }) {
  return (
    <ol className="relative space-y-5 ps-6">
      {/* rail */}
      <span className="absolute inset-y-1 start-[7px] w-px bg-navy-100" aria-hidden />
      {items.map((item, idx) => (
        <li key={item.id} className="relative animate-rise" style={{ animationDelay: `${idx * 90}ms` }}>
          <span
            className={`absolute top-1 grid h-4 w-4 place-items-center rounded-full ring-4 ${DOT_TONE[item.tone ?? "navy"]} ${item.current ? "ring-[6px] animate-pulse-gold" : ""}`}
            style={{ insetInlineStart: "-1.5rem", marginInlineStart: "-1px" }}
          >
            {item.icon ? <span className="text-white">{item.icon}</span> : null}
          </span>
          <p className="text-sm font-semibold text-ink-900">{item.title}</p>
          {item.subtitle ? <p className="mt-0.5 text-sm text-ink-500">{item.subtitle}</p> : null}
        </li>
      ))}
    </ol>
  );
}

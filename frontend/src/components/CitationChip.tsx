import { ExternalLink } from "lucide-react";

/** A traceable citation: opens the real source URL. Used in roadmap, resources and the causal chain. */
export function CitationChip({ url, label }: { url: string; label?: string }) {
  let host = label;
  if (!host) {
    try {
      host = new URL(url).hostname.replace(/^www\./, "");
    } catch {
      host = url;
    }
  }
  return (
    <a
      href={url}
      target="_blank"
      rel="noreferrer"
      className="chip max-w-full border border-navy-200 bg-navy-50 text-navy-700 transition hover:border-navy-400 hover:bg-navy-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-400"
    >
      <ExternalLink size={13} className="shrink-0" />
      <span className="truncate">{host}</span>
    </a>
  );
}

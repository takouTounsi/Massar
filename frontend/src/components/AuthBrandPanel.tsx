import { Compass } from "lucide-react";
import { STAGE_ORDER } from "../lib/diagnosis";
import { useI18n } from "../i18n/useI18n";

export function AuthBrandPanel({
  headline,
  subhead,
}: {
  headline?: string;
  subhead?: string;
}) {
  const { t, label } = useI18n();

  const resolvedHeadline = headline ?? t("auth.brandHeadline");
  const resolvedSubhead = subhead ?? t("auth.brandSubhead");

  return (
    <div
      className="relative hidden flex-col overflow-hidden p-12 lg:flex"
      style={{
        background:
          "linear-gradient(135deg, #0A1B34 0%, #13294B 50%, #1A3A66 100%)",
      }}
    >
      {/* Particle dots */}
      <div aria-hidden className="pointer-events-none absolute inset-0">
        {Array.from({ length: 28 }).map((_, i) => (
          <span
            key={i}
            className="absolute rounded-full bg-white"
            style={{
              width: Math.random() * 3 + 1 + "px",
              height: Math.random() * 3 + 1 + "px",
              left: Math.random() * 100 + "%",
              top: Math.random() * 100 + "%",
              opacity: Math.random() * 0.25 + 0.05,
              animation: `drift ${8 + Math.random() * 14}s linear infinite`,
              animationDelay: `-${Math.random() * 20}s`,
            }}
          />
        ))}
      </div>

      {/* Logo — pinned to top */}
      <div className="relative z-10 flex items-center gap-3">
        <div className="grid h-10 w-10 place-items-center rounded-xl bg-flag-600 shadow-lg">
          <Compass size={20} className="text-white" />
        </div>
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.12em] text-navy-200">
            {t("auth.brandEyebrow")}
          </p>
          <h1 className="text-lg font-medium text-white">MASSAR</h1>
        </div>
      </div>

      {/* Centered content — headline + stages */}
      <div className="relative z-10 flex flex-1 flex-col justify-center">
        <h2
          className="text-4xl font-medium leading-tight text-white mb-4"
          style={{ letterSpacing: "-0.02em" }}
        >
          {resolvedHeadline}
        </h2>
        <p className="text-base text-navy-200 leading-relaxed max-w-sm">
          {resolvedSubhead}
        </p>

        {/* Stage progress visualization */}
        <div className="mt-10">
          <p className="text-xs font-medium uppercase tracking-[0.1em] text-white/40 mb-4">
            {t("auth.stagesCaption")}
          </p>
          <div className="flex items-center gap-0">
            {STAGE_ORDER.map((stage, i) => (
              <div key={stage} className="flex items-center">
                <div className="flex flex-col items-center gap-2">
                  <div
                    className="rounded-full transition-all"
                    style={{
                      width: i === 0 ? "12px" : "8px",
                      height: i === 0 ? "12px" : "8px",
                      background:
                        i === 0
                          ? "#E4002B"
                          : i < 3
                            ? "rgba(255,255,255,0.4)"
                            : "rgba(255,255,255,0.15)",
                      boxShadow:
                        i === 0 ? "0 0 12px rgba(228,0,43,0.6)" : "none",
                    }}
                  />
                  <p className="text-[10px] text-white/40 whitespace-nowrap">
                    {label("stage", stage)}
                  </p>
                </div>
                {i < STAGE_ORDER.length - 1 && (
                  <div
                    className="h-px mb-6 mx-1"
                    style={{
                      width: "32px",
                      background:
                        i < 1 ? "rgba(228,0,43,0.5)" : "rgba(255,255,255,0.15)",
                    }}
                  />
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      <style>{`
        @keyframes drift {
          0% { transform: translateY(0px); }
          50% { transform: translateY(-20px); }
          100% { transform: translateY(0px); }
        }
      `}</style>
    </div>
  );
}

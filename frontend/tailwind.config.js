/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Sovereign navy — brand ground, authority, structure
        navy: {
          50: "#EEF2F9",
          100: "#E7EDF6",
          200: "#C7D3E8",
          300: "#9DB0D2",
          400: "#5C77A8",
          500: "#2E4D80",
          600: "#1A3A66",
          700: "#13294B",
          800: "#0D1F3A",
          900: "#0A1B34"
        },
        // Tunisian flag red — RESERVED for gap / contradiction / anomaly / stage-blocking
        flag: {
          50: "#FDE8EC",
          100: "#FBD0D9",
          200: "#F5A3B4",
          400: "#EE3D5E",
          600: "#E4002B",
          700: "#B80021",
          800: "#8F0019"
        },
        // Evidence / confirmed / on-track
        evidence: {
          50: "#E6F4F0",
          100: "#CCE9E2",
          400: "#3DAE93",
          600: "#0E8C74",
          700: "#0A6E5B",
          800: "#075345"
        },
        // Unverified / low-confidence / provisional
        caution: {
          50: "#FBF1DE",
          100: "#F6E2BC",
          400: "#D6A23C",
          600: "#B7791F",
          700: "#8F5E18"
        },
        // Collectible / unlocked / achievement accent
        gold: {
          50: "#FBF4E0",
          100: "#F6E7BC",
          300: "#E9C765",
          400: "#DDB23C",
          500: "#C8961C",
          600: "#A87A12"
        },
        paper: "#F7F8FA",
        ink: {
          900: "#0F1B2D",
          700: "#2C3A50",
          500: "#5A6577",
          400: "#8893A4"
        }
      },
      fontFamily: {
        sans: ["Inter", "IBM Plex Sans Arabic", "ui-sans-serif", "system-ui", "sans-serif"],
        arabic: ["IBM Plex Sans Arabic", "Inter", "ui-sans-serif", "sans-serif"]
      },
      fontSize: {
        overline: ["0.6875rem", { lineHeight: "1rem", letterSpacing: "0.08em" }],
        display: ["2rem", { lineHeight: "2.5rem", letterSpacing: "-0.02em" }]
      },
      borderRadius: {
        card: "14px"
      },
      boxShadow: {
        trust: "0 1px 2px rgba(10, 27, 52, 0.04), 0 8px 24px -12px rgba(10, 27, 52, 0.12)",
        "trust-lg": "0 2px 4px rgba(10, 27, 52, 0.05), 0 24px 48px -20px rgba(10, 27, 52, 0.22)",
        "glow-flag": "0 0 0 1px rgba(228,0,43,0.4), 0 0 24px -2px rgba(228,0,43,0.55)",
        "glow-evidence": "0 0 0 1px rgba(14,140,116,0.4), 0 0 24px -4px rgba(14,140,116,0.5)",
        "glow-gold": "0 0 0 1px rgba(200,150,28,0.5), 0 0 28px -4px rgba(221,178,60,0.6)",
        "glow-navy": "0 0 0 1px rgba(93,119,168,0.4), 0 0 32px -6px rgba(46,77,128,0.7)"
      },
      transitionTimingFunction: {
        sovereign: "cubic-bezier(0.2, 0.8, 0.2, 1)"
      },
      keyframes: {
        "reveal-up": {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" }
        },
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" }
        },
        // Glow breathing — for the weakest link / live signals (no bounce)
        "pulse-glow": {
          "0%, 100%": { boxShadow: "0 0 0 0 rgba(228,0,43,0.0)", borderColor: "rgba(228,0,43,0.45)" },
          "50%": { boxShadow: "0 0 22px -2px rgba(228,0,43,0.55)", borderColor: "rgba(228,0,43,0.95)" }
        },
        "pulse-gold": {
          "0%, 100%": { boxShadow: "0 0 0 0 rgba(221,178,60,0.0)" },
          "50%": { boxShadow: "0 0 26px -2px rgba(221,178,60,0.7)" }
        },
        // Node unlock — scale + opacity, no bounce
        "unlock": {
          "0%": { opacity: "0.4", transform: "scale(0.92)", filter: "blur(2px)" },
          "100%": { opacity: "1", transform: "scale(1)", filter: "blur(0)" }
        },
        // Cause→effect arrow draws in
        "draw": {
          from: { strokeDashoffset: "1" },
          to: { strokeDashoffset: "0" }
        },
        "rise": {
          from: { opacity: "0", transform: "translateY(14px) scale(0.98)" },
          to: { opacity: "1", transform: "translateY(0) scale(1)" }
        },
        // Gold shimmer sweep across collected badges
        "shimmer": {
          "0%": { backgroundPosition: "-150% 0" },
          "100%": { backgroundPosition: "250% 0" }
        },
        "scan": {
          "0%": { transform: "translateY(-100%)", opacity: "0" },
          "50%": { opacity: "1" },
          "100%": { transform: "translateY(220%)", opacity: "0" }
        }
      },
      animation: {
        "reveal-up": "reveal-up 0.3s cubic-bezier(0.2, 0.8, 0.2, 1) both",
        "fade-in": "fade-in 0.4s ease both",
        "pulse-glow": "pulse-glow 2.4s ease-in-out infinite",
        "pulse-gold": "pulse-gold 2.6s ease-in-out infinite",
        "unlock": "unlock 0.4s cubic-bezier(0.2, 0.8, 0.2, 1) both",
        "draw": "draw 0.5s ease forwards",
        "rise": "rise 0.4s cubic-bezier(0.2, 0.8, 0.2, 1) both",
        "shimmer": "shimmer 2.5s linear infinite",
        "scan": "scan 1.6s ease-in-out"
      }
    }
  },
  plugins: []
};

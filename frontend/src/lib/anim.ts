import type { Transition, Variants } from "framer-motion";

/**
 * Shared Framer Motion contract for the MASSAR redesign.
 *
 * Every page enters with `sectionVariants` staggered by child index, producing
 * the cascade reveal that makes navigation feel alive. Reduced-motion is handled
 * by Framer's own `useReducedMotion()` at the call site (or the global CSS guard
 * in styles.css), so these variants stay declarative.
 */

/** Standard enter animation for content sections. Pass the child index as `custom`. */
export const sectionVariants: Variants = {
  hidden: { opacity: 0, y: 12 },
  visible: (i = 0) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.06, duration: 0.3, ease: "easeOut" }
  })
};

/** Lighter horizontal entry — used for chips / ledger rows sliding in. */
export const slideInVariants: Variants = {
  hidden: { opacity: 0, x: 20 },
  visible: (i = 0) => ({
    opacity: 1,
    x: 0,
    transition: { delay: i * 0.04, duration: 0.25, ease: "easeOut" }
  })
};

/** SWOT / list bullet entry. */
export const bulletVariants: Variants = {
  hidden: { opacity: 0, x: -8 },
  visible: (i = 0) => ({
    opacity: 1,
    x: 0,
    transition: { delay: i * 0.04, duration: 0.22, ease: "easeOut" }
  })
};

/** useSpring config for score / readiness count-ups. */
export const springConfig = { stiffness: 60, damping: 20 };

/** Card hover lift — spread onto a motion element. */
export const cardHover = {
  whileHover: { y: -3, transition: { duration: 0.15, ease: "easeOut" } }
} as const;

/** Stronger lift for collectible resource badges. */
export const badgeHover = {
  whileHover: { y: -4, transition: { duration: 0.18, ease: "easeOut" } }
} as const;

/** Unlock pulse for newly-unlocked roadmap nodes. */
export const unlockPulse = {
  initial: { boxShadow: "0 0 0 0 rgba(36,160,122,0)" },
  animate: {
    boxShadow: [
      "0 0 0 0 rgba(36,160,122,0)",
      "0 0 0 8px rgba(36,160,122,0.3)",
      "0 0 0 0 rgba(36,160,122,0)"
    ]
  },
  transition: { duration: 0.8, ease: "easeOut" } as Transition
};

/** AnimatePresence height reveal for inline expansions (blockers, scores, anomalies). */
export const expandReveal = {
  initial: { height: 0, opacity: 0 },
  animate: { height: "auto", opacity: 1 },
  exit: { height: 0, opacity: 0 },
  transition: { duration: 0.2, ease: "easeOut" } as Transition
} as const;

/** Standard transition for staggered parents. */
export const staggerParent: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.06 } }
};

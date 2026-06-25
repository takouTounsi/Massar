import { motion, useReducedMotion } from "framer-motion";

/**
 * A short radial burst of green dots from the node centre — the reward beat
 * when a roadmap node unlocks. Render conditionally; it self-expires visually.
 * Suppressed under reduced-motion.
 */
export function ParticleBurst({ count = 6 }: { count?: number }) {
  const reduced = useReducedMotion();
  if (reduced) return null;
  const dots = Array.from({ length: count });
  return (
    <span aria-hidden className="pointer-events-none absolute inset-0 grid place-items-center">
      {dots.map((_, i) => {
        const angle = (i / count) * Math.PI * 2;
        const dx = Math.cos(angle) * 26;
        const dy = Math.sin(angle) * 26;
        return (
          <motion.span
            key={i}
            className="absolute h-1.5 w-1.5 rounded-full bg-evidence-500"
            initial={{ scale: 0, x: 0, y: 0, opacity: 1 }}
            animate={{ scale: [0, 1, 0.8], x: dx, y: dy, opacity: [1, 1, 0] }}
            transition={{ duration: 0.6, ease: "easeOut" }}
          />
        );
      })}
    </span>
  );
}

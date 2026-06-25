import { useSyncExternalStore } from "react";

const KEY = "massar_saved_resources";
const listeners = new Set<() => void>();

function read(): Set<string> {
  if (typeof window === "undefined") return new Set();
  try {
    const raw = window.localStorage.getItem(KEY);
    return new Set(raw ? (JSON.parse(raw) as string[]) : []);
  } catch {
    return new Set();
  }
}

let cache = read();

function emit() {
  listeners.forEach((listener) => listener());
}

export function toggleSaved(id: string) {
  const next = new Set(cache);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  cache = next;
  try {
    window.localStorage.setItem(KEY, JSON.stringify([...next]));
  } catch {
    /* ignore quota / private mode */
  }
  emit();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Collected (saved) resource ids — the founder's badge collection. Persists in localStorage. */
export function useSavedResources() {
  const saved = useSyncExternalStore(subscribe, () => cache, () => cache);
  return { saved, toggleSaved };
}

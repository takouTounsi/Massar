import { PlusCircle } from "lucide-react";
import type { ReactNode } from "react";

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="panel grid place-items-center p-8 text-center">
      <PlusCircle className="mb-3 text-ink-400" size={28} />
      <h3 className="font-semibold text-ink-900">{title}</h3>
      {children ? <p className="mt-1 max-w-md text-sm text-ink-500">{children}</p> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

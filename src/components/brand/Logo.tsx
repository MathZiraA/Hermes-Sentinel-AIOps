import { cn } from "@/lib/utils";

/** Marca do Hermes Sentinel: um escudo com uma linha de pulso (vigiar + saúde do sistema). */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden className={cn("h-8 w-8", className)}>
      <rect width="32" height="32" rx="9" className="fill-primary" />
      <path
        d="M16 6.5 24 9.6v6.2c0 4.9-3.3 8.6-8 10.2-4.7-1.6-8-5.3-8-10.2V9.6z"
        className="fill-primary-foreground/15 stroke-primary-foreground"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path
        d="M10.5 16.4h2.6l1.5-3.2 2.4 6.2 1.6-3h2.9"
        fill="none"
        className="stroke-primary-foreground"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <span className="flex items-center gap-2.5">
      <LogoMark />
      {!compact && (
        <span className="leading-tight">
          <span className="block text-[13px] font-semibold tracking-tight text-foreground">
            Hermes Sentinel
          </span>
          <span className="block text-[11px] text-muted-foreground">AIOps · Kubernetes</span>
        </span>
      )}
    </span>
  );
}

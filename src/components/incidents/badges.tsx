import { AlertTriangle, CheckCircle2, Clock } from "lucide-react";
import type { IncidentStatus, Sev, Sla } from "@/lib/api/types";
import { useI18n } from "@/lib/i18n/i18n";
import { cn } from "@/lib/utils";

const SEV_STYLE: Record<Sev, string> = {
  SEV1: "bg-sev1/15 text-sev1 ring-sev1/30",
  SEV2: "bg-sev2/15 text-sev2 ring-sev2/30",
  SEV3: "bg-sev3/15 text-sev3 ring-sev3/30",
  SEV4: "bg-sev4/15 text-sev4 ring-sev4/30",
};

export function SevBadge({ sev, className }: { sev: Sev; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-1.5 py-0.5 font-mono text-[11px] font-semibold ring-1 ring-inset",
        SEV_STYLE[sev],
        className,
      )}
    >
      {sev}
    </span>
  );
}

const STATUS_TONE: Record<IncidentStatus, string> = {
  detected: "bg-sev2/15 text-sev2",
  acknowledged: "bg-sev4/15 text-sev4",
  investigating: "bg-sev4/15 text-sev4",
  waiting_approval: "bg-sev3/20 text-foreground",
  remediating: "bg-primary/15 text-primary",
  monitoring: "bg-primary/15 text-primary",
  resolved: "bg-success/15 text-success",
  postmortem: "bg-success/15 text-success",
  closed: "bg-muted text-muted-foreground",
  failed: "bg-destructive/15 text-destructive",
};

export function StatusBadge({ status, label }: { status: IncidentStatus; label: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-medium",
        STATUS_TONE[status],
      )}
    >
      {status === "waiting_approval" && (
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-sev3" />
      )}
      {label}
    </span>
  );
}

export function SlaBadge({ sla, open }: { sla: Sla; open: boolean }) {
  const { t, formatRelative } = useI18n();
  if (sla.resolveBreached || sla.ackBreached) {
    return (
      <span className="inline-flex items-center gap-1 text-[11px] font-medium text-destructive">
        <AlertTriangle className="h-3.5 w-3.5" aria-hidden />
        {sla.resolveBreached ? t("sla.resolveLate") : t("sla.ackLate")}
      </span>
    );
  }
  if (!open) {
    return (
      <span className="inline-flex items-center gap-1 text-[11px] text-success">
        <CheckCircle2 className="h-3.5 w-3.5" aria-hidden /> {t("sla.ok")}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
      <Clock className="h-3.5 w-3.5" aria-hidden /> {t("sla.due")}{" "}
      {formatRelative(sla.resolveDueAt)}
    </span>
  );
}

import { cn } from "@/lib/utils";
import { agentClass, type Accessory, type AgentColor } from "./agents";

/** Glossy plastic pill-shaped agent. Pure CSS; ~48x76 px. */
export function AgentFigure({
  color, accessory, seated, size = 1,
}: { color: AgentColor; accessory?: Accessory; seated?: boolean; size?: number }) {
  return (
    <div className={cn("relative", agentClass(color))} style={{ width: 48 * size, height: 76 * size }}>
      <div className="absolute bottom-0 left-0 origin-bottom-left" style={{ transform: `scale(${size})`, width: 48, height: 76 }}>
        {/* antenna */}
        <div className="absolute left-1/2 top-0 h-3 w-[2px] -translate-x-1/2 rounded-full bg-ink-soft/40" />
        <div className="agent-body absolute left-1/2 top-[-4px] h-[9px] w-[9px] -translate-x-1/2 rounded-full" />

        {/* legs */}
        {!seated && (
          <>
            <div className="agent-limb absolute bottom-0 left-[14px] h-[12px] w-[9px]" />
            <div className="agent-limb absolute bottom-0 right-[14px] h-[12px] w-[9px]" />
          </>
        )}

        {/* arms */}
        <div className="agent-limb absolute left-[1px] top-[36px] h-[18px] w-[9px] -rotate-[18deg]" />
        <div className="agent-limb absolute right-[1px] top-[36px] h-[18px] w-[9px] rotate-[18deg]" />

        {/* body */}
        <div className="agent-body absolute left-[6px] top-[9px] h-[58px] w-[36px]">
          {/* face plate */}
          <div className="absolute left-1/2 top-[10px] flex -translate-x-1/2 gap-[5px]">
            <div className="agent-eye anim-blink h-[9px] w-[9px] rounded-full" />
            <div className="agent-eye anim-blink h-[9px] w-[9px] rounded-full" />
          </div>
          <div className="agent-blush absolute left-[3px] top-[20px] h-[7px] w-[9px]" />
          <div className="agent-blush absolute right-[3px] top-[20px] h-[7px] w-[9px]" />
          <div className="absolute left-1/2 top-[23px] h-[3px] w-[8px] -translate-x-1/2 rounded-b-full bg-ink-soft/60" />
        </div>

        {accessory === "headset" && (
          <>
            <div className="absolute left-[4px] top-[8px] h-[16px] w-[40px] rounded-t-full border-[2.5px] border-b-0 border-screen/80" />
            <div className="absolute left-[2px] top-[19px] h-[10px] w-[6px] rounded-full bg-screen/85" />
            <div className="absolute right-[2px] top-[19px] h-[10px] w-[6px] rounded-full bg-screen/85" />
          </>
        )}
        {accessory === "cap" && (
          <div className="absolute left-[8px] top-[6px] h-[9px] w-[34px] rounded-t-full bg-screen/85">
            <div className="absolute -right-[6px] bottom-0 h-[3px] w-[14px] rounded-full bg-screen/85" />
            <div className="agent-fill absolute left-1/2 top-[2px] h-[4px] w-[4px] -translate-x-1/2 rounded-full" />
          </div>
        )}
        {accessory === "papers" && (
          <div className="absolute left-[9px] top-[40px] h-[17px] w-[30px] -rotate-6">
            <div className="absolute inset-0 translate-x-[2px] -translate-y-[3px] rotate-6 rounded-[2px] bg-card shadow-card" />
            <div className="absolute inset-0 rounded-[2px] bg-card shadow-card">
              <div className="mx-1 mt-[3px] h-[2px] rounded bg-muted-foreground/40" />
              <div className="mx-1 mt-[2px] h-[2px] w-3/5 rounded bg-muted-foreground/40" />
              <div className="mx-1 mt-[2px] h-[2px] w-4/5 rounded bg-agent-green/60" />
            </div>
          </div>
        )}
        {accessory === "marker" && (
          <div className="absolute -right-[3px] top-[30px] h-[16px] w-[5px] rotate-[25deg] rounded-full bg-agent-purple shadow-card">
            <div className="h-[5px] rounded-t-full bg-screen/80" />
          </div>
        )}
        {accessory === "key" && (
          <div className="absolute -left-[6px] top-[44px] -rotate-[20deg]">
            <div className="vault-dial h-[9px] w-[9px] rounded-full" />
            <div className="vault-dial -mt-[3px] ml-[3px] h-[10px] w-[3px] rounded" />
          </div>
        )}
      </div>
    </div>
  );
}

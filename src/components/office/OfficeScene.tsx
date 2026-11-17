import { Fragment, useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { AgentFigure } from "./AgentFigure";
import { AGENTS, agentClass, type Agent } from "./agents";
import { Billboard, Decal, FLOOR, IsoBox, project } from "./iso";

const WALL_H = 150;
const SCENE_W = 1100;
const SCENE_H = 800;

function useFitScale(ref: React.RefObject<HTMLDivElement | null>) {
  const [scale, setScale] = useState(0.8);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setScale(Math.max(0.4, Math.min(width / SCENE_W, height / SCENE_H, 1.25)));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);
  return scale;
}

export function OfficeScene() {
  const ref = useRef<HTMLDivElement>(null);
  const scale = useFitScale(ref);
  const [focus, setFocus] = useState<string | null>(null);

  return (
    <div ref={ref} className="iso-canvas relative h-full w-full overflow-hidden">
      <div className="iso-dots pointer-events-none absolute inset-0 opacity-60" />
      <div className="absolute left-1/2 top-1/2" style={{ transform: `translate(0, 60px) scale(${scale})` }}>
        {/* ---------- 3D world ---------- */}
        <div
          className="iso-world"
          style={{
            left: -FLOOR / 2,
            top: -FLOOR / 2,
            width: FLOOR,
            height: FLOOR,
            transform: "rotateX(60deg) rotateZ(-45deg)",
          }}
        >
          <World />
          {AGENTS.map((a) => (
            <AgentSprite key={a.id} agent={a} active={focus === a.id} onFocus={setFocus} />
          ))}
        </div>

        {/* ---------- 2D overlay: speech bubbles always on top ---------- */}
        {AGENTS.map((a) => (
          <AgentBubble key={a.id} agent={a} active={focus === a.id} />
        ))}
      </div>
    </div>
  );
}

/* ---------------- Agents ---------------- */

function AgentSprite({ agent, active, onFocus }: { agent: Agent; active: boolean; onFocus: (id: string | null) => void }) {
  return (
    <>
      <Decal x={agent.x - 22} y={agent.y - 22} z={agent.z + 0.6} w={44} d={44}>
        <div className="iso-contact-shadow anim-bob-shadow h-full w-full rounded-full" style={{ animationDelay: `${agent.delay}s` }} />
      </Decal>
      {active && (
        <Decal x={agent.x - 30} y={agent.y - 30} z={agent.z + 0.8} w={60} d={60}>
          <div className={cn("agent-ring h-full w-full rounded-full", agentClass(agent.color))} />
        </Decal>
      )}
      <Billboard x={agent.x} y={agent.y} z={agent.z} width={56} height={84}>
        <button
          type="button"
          aria-label={`${agent.name}: ${agent.activity}`}
          onMouseEnter={() => onFocus(agent.id)}
          onMouseLeave={() => onFocus(null)}
          onFocus={() => onFocus(agent.id)}
          onBlur={() => onFocus(null)}
          className="anim-bob absolute bottom-[2px] left-1/2 -ml-6 cursor-pointer outline-none"
          style={{ animationDelay: `${agent.delay}s` }}
        >
          <AgentFigure color={agent.color} accessory={agent.accessory} seated={agent.seated} />
        </button>
      </Billboard>
    </>
  );
}

function AgentBubble({ agent, active }: { agent: Agent; active: boolean }) {
  const p = project(agent.x, agent.y, agent.z);
  return (
    <div className="pointer-events-none absolute" style={{ left: p.left, top: p.top - 92, zIndex: active ? 20 : 10 }}>
      <div className="anim-bob" style={{ animationDelay: `${agent.delay}s` }}>
        <div
          className={cn(
            "bubble-tail relative -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-xl bg-bubble px-2.5 py-1.5 shadow-bubble transition-transform duration-200",
            agentClass(agent.color),
            active && "scale-110",
          )}
        >
          <div className="flex items-center gap-1.5">
            <span className="agent-fill h-1.5 w-1.5 rounded-full" />
            <span className="agent-text text-[9px] font-semibold uppercase tracking-[0.12em]">{agent.name}</span>
            <span className="flex gap-[2px]">
              {[0, 1, 2].map((i) => (
                <span key={i} className="anim-type h-[3px] w-[3px] rounded-full bg-muted-foreground" style={{ animationDelay: `${i * 0.15}s` }} />
              ))}
            </span>
          </div>
          <div className="mt-0.5 text-[11px] font-medium text-foreground">{agent.activity}</div>
        </div>
      </div>
    </div>
  );
}

/* ---------------- World ---------------- */

function World() {
  return (
    <>
      {/* Floor slab */}
      <IsoBox
        x={0}
        y={0}
        z={-26}
        w={FLOOR}
        d={FLOOR}
        h={26}
        mat="mat-trim"
        topClassName="iso-floor-tiles"
      />

      <Zones />
      <Paths />
      <Walls />
      <Workstation />
      <WhiteboardZone />
      <VaultZone />
      <SecurityGate />
      <ServerRack />
      <Plant x={655} y={40} />
      <Plant x={40} y={300} />
      <Plant x={40} y={500} small />
      <Rug />
    </>
  );
}

function Zones() {
  const zones = [
    { x: 30, y: 30, w: 320, d: 230, c: "zone-blue", label: "WORKSTATION", pos: "bottom-2 right-4" },
    { x: 380, y: 30, w: 240, d: 160, c: "zone-purple", label: "WHITEBOARD", pos: "bottom-2 left-4" },
    { x: 470, y: 380, w: 230, d: 230, c: "zone-orange", label: "VAULT", pos: "bottom-2 left-4" },
    { x: 30, y: 540, w: 300, d: 160, c: "zone-yellow", label: "SECURITY GATE", pos: "bottom-2 left-4" },
  ];
  return (
    <>
      {zones.map((z) => (
        <Decal key={z.label} x={z.x} y={z.y} w={z.w} d={z.d} className={z.c}>
          <div className="zone-patch h-full w-full rounded-[22px]" />
          <div className={cn("zone-label absolute text-[13px]", z.pos)} data-x=" font-bold tracking-[0.25em]">{z.label}</div>
        </Decal>
      ))}
    </>
  );
}

function Paths() {
  return (
    <Decal x={0} y={0} z={0.7} w={FLOOR} d={FLOOR}>
      <svg viewBox={`0 0 ${FLOOR} ${FLOOR}`} className="h-full w-full overflow-visible">
        <g fill="none" strokeWidth="4" strokeLinecap="round" strokeDasharray="2 18" className="anim-dash">
          <path d="M360 370 Q 280 300 200 230" className="stroke-agent-blue" />
          <path d="M360 370 Q 430 230 495 150" className="stroke-agent-purple" />
          <path d="M360 370 Q 450 450 515 500" className="stroke-agent-orange" />
          <path d="M360 370 Q 300 500 270 600" className="stroke-agent-yellow" />
        </g>
      </svg>
    </Decal>
  );
}

function Rug() {
  return (
    <Decal x={300} y={310} w={120} d={120} z={0.55}>
      <div className="h-full w-full rounded-full border-[6px] border-agent-green/25 bg-agent-green/10" />
    </Decal>
  );
}

function Walls() {
  return (
    <>
      {/* north wall (back-left) */}
      <IsoBox
        x={0}
        y={0}
        w={FLOOR}
        d={14}
        h={WALL_H}
        mat="mat-wall"
        south={
          <div className="relative h-full w-full">
            <div className="absolute inset-x-0 bottom-0 h-3 bg-mat-trim" />
            <div className="window-surface absolute left-[70px] top-[18px] h-[48px] w-[200px] rounded-md border-4 border-card" />
            {/* wall clock */}
            <div className="absolute left-[660px] top-[24px] h-9 w-9 rounded-full border-[3px] border-screen/70 bg-card">
              <div className="absolute left-1/2 top-[6px] h-[11px] w-[2px] -translate-x-1/2 rounded bg-screen" />
              <div className="absolute left-1/2 top-1/2 h-[2px] w-[9px] rounded bg-agent-orange" />
            </div>
          </div>
        }
      />
      {/* east wall (back-right) */}
      <IsoBox
        x={FLOOR - 14}
        y={0}
        w={14}
        d={FLOOR}
        h={WALL_H}
        mat="mat-wall"
        west={
          <div className="relative h-full w-full">
            <div className="absolute inset-x-0 bottom-0 h-3 bg-mat-trim" />
            <div className="absolute left-[30px] top-[22px] text-[15px] font-extrabold tracking-[0.35em] text-ink-soft/70">
              AGENT FACTORY
            </div>
            <div className="absolute left-[30px] top-[44px] h-1 w-[90px] rounded-full progress-rainbow" />
            {[318, 592].map((l) => (
              <div key={l} className="window-surface absolute top-[20px] h-[76px] w-[110px] rounded-md border-4 border-card" style={{ left: l }}>
                <div className="absolute inset-y-0 left-1/2 w-1 -translate-x-1/2 bg-card" />
              </div>
            ))}
          </div>
        }
      />
    </>
  );
}

function Workstation() {
  const deskZ = 56;
  return (
    <>
      {/* desk legs + drawer cabinet */}
      <IsoBox x={58} y={50} w={8} d={8} h={deskZ} mat="mat-metal" />
      <IsoBox x={58} y={128} w={8} d={8} h={deskZ} mat="mat-metal" />
      <IsoBox
        x={262}
        y={50}
        w={68}
        d={86}
        h={deskZ}
        mat="mat-white"
        shadow
        south={
          <div className="flex h-full flex-col gap-1.5 p-1.5">
            <div className="flex-1 rounded-sm border border-border bg-card/60" />
            <div className="flex-1 rounded-sm border border-border bg-card/60" />
          </div>
        }
      />
      {/* desk top */}
      <IsoBox x={50} y={44} z={deskZ} w={286} d={98} h={9} mat="mat-wood" shadow />
      {/* monitors */}
      {[86, 168].map((mx, i) => (
        <Fragment key={mx}>
          <IsoBox x={mx + 30} y={70} z={deskZ + 9} w={12} d={10} h={14} mat="mat-dark" />
          <IsoBox
            x={mx}
            y={78}
            z={deskZ + 21}
            w={74}
            d={5}
            h={50}
            mat="mat-dark"
            south={<Screen variant={i} />}
          />
        </Fragment>
      ))}
      {/* keyboard + mug */}
      <IsoBox x={120} y={104} z={deskZ + 9} w={70} d={18} h={3} mat="mat-white" />
      <IsoBox x={274} y={92} z={deskZ + 9} w={14} d={14} h={14} mat="mat-blue" />
      {/* stool under Atlas */}
      <IsoBox x={176} y={186} w={28} d={28} h={30} mat="mat-dark" />
      <IsoBox x={170} y={180} z={26} w={40} d={40} h={6} mat="mat-blue" />
    </>
  );
}

function Screen({ variant }: { variant: number }) {
  const rows = variant === 0 ? [70, 45, 85, 30, 60] : [40, 80, 55, 65, 35];
  const tones = ["bg-agent-blue", "bg-agent-green", "bg-agent-purple", "bg-agent-yellow", "bg-agent-orange"];
  return (
    <div className="screen-surface m-[3px] flex h-[calc(100%-6px)] flex-col gap-[4px] rounded-[3px] p-[5px]">
      {rows.map((w, i) => (
        <div key={i} className={cn("h-[3px] rounded-full opacity-80", tones[(i + variant) % 5])} style={{ width: `${w}%`, marginLeft: i % 2 ? 6 : 0 }} />
      ))}
    </div>
  );
}

function WhiteboardZone() {
  const notes = [
    ["bg-agent-yellow", "bg-agent-blue", "bg-agent-green"],
    ["bg-agent-orange", "bg-agent-purple"],
    ["bg-agent-green", "bg-agent-yellow", "bg-agent-blue"],
  ];
  return (
    <>
      <IsoBox
        x={395}
        y={14}
        z={36}
        w={210}
        d={6}
        h={96}
        mat="mat-metal"
        south={
          <div className="whiteboard-surface m-[4px] flex h-[calc(100%-8px)] gap-2 rounded-[3px] p-2">
            {notes.map((col, i) => (
              <div key={i} className="flex flex-1 flex-col gap-1.5 border-r border-dashed border-border pr-1.5 last:border-r-0">
                <div className="h-[3px] w-3/4 rounded-full bg-ink-soft/50" />
                {col.map((c, j) => (
                  <div key={j} className={cn("h-[14px] rounded-[2px] opacity-85 shadow-card", c)} style={{ transform: `rotate(${(j % 2 ? 1 : -1) * 3}deg)` }} />
                ))}
              </div>
            ))}
          </div>
        }
      />
      {/* marker tray */}
      <IsoBox x={410} y={20} z={34} w={180} d={8} h={3} mat="mat-metal" />
      {/* side table with markers */}
      <IsoBox x={565} y={110} w={34} d={34} h={36} mat="mat-white" shadow />
      <IsoBox x={572} y={118} z={36} w={6} d={6} h={14} mat="mat-purple" />
      <IsoBox x={584} y={122} z={36} w={6} d={6} h={14} mat="mat-blue" />
    </>
  );
}

function VaultZone() {
  return (
    <>
      <IsoBox
        x={580}
        y={420}
        w={120}
        d={140}
        h={136}
        mat="mat-vault"
        shadow
        top={<div className="m-3 h-[calc(100%-24px)] rounded-md border-2 border-card/40" />}
        west={
          <div className="relative h-full w-full">
            <div className="vault-door absolute left-1/2 top-1/2 h-[96px] w-[96px] -translate-x-1/2 -translate-y-1/2 rounded-full">
              <div className="vault-dial absolute left-1/2 top-1/2 h-7 w-7 -translate-x-1/2 -translate-y-1/2 rounded-full" />
              {[0, 60, 120].map((r) => (
                <div key={r} className="absolute left-1/2 top-1/2 h-[3px] w-[60px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-mat-gold/70" style={{ transform: `translate(-50%,-50%) rotate(${r}deg)` }} />
              ))}
            </div>
            <div className="absolute right-3 top-3 h-2 w-2 rounded-full bg-success anim-led" />
          </div>
        }
        south={
          <div className="flex h-full items-end justify-center pb-3">
            <div className="rounded bg-card/70 px-2 py-0.5 text-[9px] font-bold tracking-[0.3em] text-ink-soft">VAULT</div>
          </div>
        }
      />
      {/* gold bars */}
      <IsoBox x={600} y={590} w={40} d={18} h={10} mat="mat-gold" shadow />
      <IsoBox x={606} y={612} w={40} d={18} h={10} mat="mat-gold" />
      <IsoBox x={603} y={598} z={10} w={40} d={18} h={10} mat="mat-gold" />
    </>
  );
}

function SecurityGate() {
  const pillar = (x: number) => (
    <IsoBox
      x={x}
      y={600}
      w={22}
      d={56}
      h={74}
      mat="mat-white"
      shadow
      west={
        <div className="flex h-full flex-col items-center gap-1.5 pt-2">
          <div className="h-1.5 w-8 rounded-full bg-success anim-led" />
          <div className="h-5 w-6 rounded-sm bg-screen/80" />
        </div>
      }
      top={<div className="m-1 h-[calc(100%-8px)] rounded-sm bg-agent-yellow/40" />}
    />
  );
  return (
    <>
      <Decal x={60} y={590} w={180} d={76} z={0.65}>
        <div className="hazard-stripes h-full w-full rounded-md opacity-70" />
      </Decal>
      {pillar(70)}
      {pillar(196)}
      {/* turnstile arm */}
      <IsoBox x={92} y={624} z={46} w={66} d={6} h={6} mat="mat-red" />
      <IsoBox x={92} y={614} z={30} w={18} d={26} h={30} mat="mat-metal" />
      {/* glass panels */}
      <IsoBox x={0} y={628} w={70} d={4} h={60} mat="mat-glass" className="opacity-80" />
      <IsoBox x={218} y={628} w={60} d={4} h={60} mat="mat-glass" className="opacity-80" />
    </>
  );
}

function ServerRack() {
  return (
    <IsoBox
      x={636}
      y={180}
      w={64}
      d={120}
      h={118}
      mat="mat-dark"
      shadow
      west={
        <div className="grid h-full grid-cols-1 gap-1.5 p-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="flex items-center gap-1.5 rounded-sm bg-screen/70 px-2">
              {["bg-agent-green", "bg-agent-blue", "bg-agent-yellow"].map((c, j) => (
                <span key={j} className={cn("anim-led h-1.5 w-1.5 rounded-full", c)} style={{ animationDelay: `${(i * 3 + j) * 0.17}s` }} />
              ))}
              <span className="ml-auto h-[3px] w-8 rounded-full bg-card/20" />
            </div>
          ))}
        </div>
      }
    />
  );
}

function Plant({ x, y, small }: { x: number; y: number; small?: boolean }) {
  const s = small ? 0.75 : 1;
  return (
    <>
      <IsoBox x={x - 16 * s} y={y - 16 * s} w={32 * s} d={32 * s} h={30 * s} mat="mat-pot" shadow />
      <Billboard x={x} y={y} z={28 * s} width={70 * s} height={70 * s}>
        <div className="relative h-full w-full">
          <div className="leaf absolute bottom-[8%] left-[8%] h-[46%] w-[46%] rounded-full" />
          <div className="leaf absolute bottom-[8%] right-[8%] h-[46%] w-[46%] rounded-full" />
          <div className="leaf absolute left-[22%] top-[6%] h-[56%] w-[56%] rounded-full" />
        </div>
      </Billboard>
    </>
  );
}

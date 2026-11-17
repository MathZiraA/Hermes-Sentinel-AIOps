import { memo, type KeyboardEvent } from "react";
import { cn } from "@/lib/utils";

export type AgentCardProps = {
  name: string;
  role: string;
  /** Avatar source. Defaults to the brief's image. */
  src?: string;
  online?: boolean;
  onSelect?: () => void;
  className?: string;
};

/** One shared physics curve for every moving part. */
const EASE = "duration-500 ease-[cubic-bezier(0.23,1,0.32,1)]";

/**
 * Agent profile card. All hover/focus states are pure CSS (`group`), and every
 * animated property is `transform` or `opacity` — the deep shadow and avatar
 * ring are separate layers that fade in, so nothing triggers layout or repaint.
 */
export const AgentCard = memo(function AgentCard({
  name,
  role,
  src = "/image_457751.jpg",
  online = true,
  onSelect,
  className,
}: AgentCardProps) {
  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onSelect?.();
    }
  };

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label="Abrir perfil do agente"
      onClick={onSelect}
      onKeyDown={onKeyDown}
      className={cn(
        "group relative w-full max-w-sm cursor-pointer rounded-3xl",
        "transform-gpu will-change-transform transition-transform",
        EASE,
        "hover:-translate-y-1.5 focus-visible:-translate-y-1.5",
        "focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 focus-visible:ring-offset-2",
        "motion-reduce:transition-none motion-reduce:hover:translate-y-0",
        className,
      )}
    >
      {/* Deep hover shadow: pre-rendered, only its opacity animates */}
      <div
        aria-hidden
        className={cn(
          "pointer-events-none absolute inset-0 rounded-3xl opacity-0 shadow-[0_20px_40px_-15px_rgba(0,0,0,0.08)]",
          "transform-gpu will-change-[opacity] transition-opacity",
          EASE,
          "group-hover:opacity-100 group-focus-visible:opacity-100",
        )}
      />

      <div className="relative overflow-hidden rounded-3xl border border-gray-100/80 bg-white p-6 shadow-sm">
        {/* Glow */}
        <div
          aria-hidden
          className={cn(
            "pointer-events-none absolute inset-0 z-0 bg-linear-to-br from-indigo-50/50 via-white to-purple-50/50 opacity-0",
            "transition-opacity",
            EASE,
            "group-hover:opacity-100 group-focus-visible:opacity-100",
          )}
        />

        <div className="relative z-10 flex items-center gap-5">
          <div className="relative shrink-0">
            <div className="relative h-16 w-16 overflow-hidden rounded-full border-2 border-transparent">
              <img
                src={src}
                alt={`Avatar de ${name}`}
                width={64}
                height={64}
                decoding="async"
                className={cn(
                  "h-full w-full rounded-full object-cover",
                  "transform-gpu will-change-transform transition-transform",
                  EASE,
                  "group-hover:scale-[1.08] group-focus-visible:scale-[1.08] motion-reduce:transition-none",
                )}
              />
            </div>
            {/* Hover ring (replaces animating border-color) */}
            <div
              aria-hidden
              className={cn(
                "pointer-events-none absolute inset-0 rounded-full ring-2 ring-inset ring-indigo-100 opacity-0",
                "transition-opacity",
                EASE,
                "group-hover:opacity-100 group-focus-visible:opacity-100",
              )}
            />
            {online && (
              <span className="absolute bottom-0.5 right-0.5 h-3 w-3 rounded-full bg-white p-0.5">
                <span className="block h-2 w-2 animate-pulse rounded-full bg-emerald-500" />
              </span>
            )}
          </div>

          <div className="min-w-0">
            <h3 className="truncate text-lg font-semibold text-slate-800 transition-colors duration-300 group-hover:text-indigo-600 group-focus-visible:text-indigo-600">
              {name}
            </h3>
            <p className="mt-0.5 truncate text-sm text-slate-500">{role}</p>
            {online && <span className="sr-only">Online</span>}
          </div>
        </div>
      </div>
    </div>
  );
});

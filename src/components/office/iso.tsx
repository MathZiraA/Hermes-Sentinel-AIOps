import type { CSSProperties, ReactNode } from "react";
import { cn } from "@/lib/utils";

/** Floor size in px (12 x 12 tiles of 60px). */
export const FLOOR = 720;

/** Projects a floor-space point (x, y on the floor, z up) to 2D screen offsets from the floor center. */
export function project(x: number, y: number, z = 0) {
  const cx = x - FLOOR / 2;
  const cy = y - FLOOR / 2;
  const k = Math.SQRT1_2;
  return { left: k * (cx + cy), top: 0.5 * k * (cy - cx) - 0.866 * z };
}

type BoxProps = {
  x: number;
  y: number;
  z?: number;
  w: number;
  d: number;
  h: number;
  mat: string;
  top?: ReactNode;
  south?: ReactNode;
  west?: ReactNode;
  shadow?: boolean;
  className?: string;
  topClassName?: string;
  southClassName?: string;
  westClassName?: string;
};

/**
 * A solid 3D box built from three faces (top, south, west) — the only faces the
 * isometric camera can see. Coordinates are in floor space.
 */
export function IsoBox({
  x,
  y,
  z = 0,
  w,
  d,
  h,
  mat,
  top,
  south,
  west,
  shadow,
  className,
  topClassName,
  southClassName,
  westClassName,
}: BoxProps) {
  return (
    <div
      className={cn("iso-obj", mat, className)}
      style={{ left: x, top: y, width: w, height: d, transform: `translateZ(${z}px)` }}
    >
      {shadow && (
        <div
          className="iso-box-shadow absolute"
          style={{
            left: -6,
            top: 4,
            width: w + 10,
            height: d + 10,
            transform: `translateZ(${-z + 0.4}px)`,
          }}
        />
      )}
      <div
        className={cn("iso-face iso-top", topClassName)}
        style={{ width: w, height: d, transform: `translateZ(${h}px)` }}
      >
        {top}
      </div>
      <div
        className={cn("iso-face iso-south", southClassName)}
        style={{
          width: w,
          height: h,
          transform: `translateY(${d}px) translateZ(${h}px) rotateX(-90deg)`,
        }}
      >
        {south}
      </div>
      <div
        className={cn("iso-face iso-west", westClassName)}
        style={{
          width: d,
          height: h,
          transform: `translateZ(${h}px) rotateZ(90deg) rotateX(-90deg)`,
        }}
      >
        {west}
      </div>
    </div>
  );
}

/** Flat element painted on the floor (or at height z), lying in the floor plane. */
export function Decal({
  x,
  y,
  z = 0.5,
  w,
  d,
  className,
  style,
  children,
}: {
  x: number;
  y: number;
  z?: number;
  w: number;
  d: number;
  className?: string;
  style?: CSSProperties;
  children?: ReactNode;
}) {
  return (
    <div
      className={cn("absolute", className)}
      style={{ left: x, top: y, width: w, height: d, transform: `translateZ(${z}px)`, ...style }}
    >
      {children}
    </div>
  );
}

/**
 * Upright sprite standing at (x, y, z): a vertical plane turned to face the camera,
 * with its bottom-center on the anchor. Height is compensated so `height` px on
 * screen equals `height` px of content.
 */
export function Billboard({
  x,
  y,
  z = 0,
  width,
  height,
  children,
  className,
}: {
  x: number;
  y: number;
  z?: number;
  width: number;
  height: number;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className="iso-anchor" style={{ left: x, top: y, transform: `translateZ(${z}px)` }}>
      <div
        className={cn("absolute left-0 top-0", className)}
        style={{
          width,
          height,
          transformOrigin: "0 0",
          transform: "rotateZ(45deg) rotateX(-90deg) scaleY(1.1547) translate(-50%, -100%)",
        }}
      >
        {children}
      </div>
    </div>
  );
}

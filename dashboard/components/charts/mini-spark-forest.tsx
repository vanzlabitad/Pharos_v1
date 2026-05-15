"use client";

import { forestPlot } from "@/lib/design-tokens";

function logScale(v: number, min: number, max: number, width: number): number {
  const logMin = Math.log10(Math.max(min, 0.001));
  const logMax = Math.log10(max);
  const logV = Math.log10(Math.max(v, min));
  return ((logV - logMin) / (logMax - logMin)) * width;
}

export function MiniSparkForest({
  lo,
  point,
  hi,
  flagged,
  width = 80,
  height = 16,
}: {
  lo: number;
  point: number;
  hi: number;
  flagged?: boolean;
  width?: number;
  height?: number;
}) {
  const { scaleMin, scaleMax, nullLine } = forestPlot;
  const mid = height / 2;

  const clampLo = Math.max(lo, scaleMin);
  const clampHi = Math.min(hi, scaleMax);
  const clampPt = Math.max(Math.min(point, scaleMax), scaleMin);

  const xLo = logScale(clampLo, scaleMin, scaleMax, width);
  const xHi = logScale(clampHi, scaleMin, scaleMax, width);
  const xPt = logScale(clampPt, scaleMin, scaleMax, width);
  const xNull = logScale(nullLine, scaleMin, scaleMax, width);

  const dotR = flagged ? 3.5 : 2.5;
  const dotColor = flagged ? "var(--accent)" : "var(--ink-300)";

  return (
    <svg width={width} height={height} className="inline-block align-middle">
      <line
        x1={xNull}
        y1={1}
        x2={xNull}
        y2={height - 1}
        stroke="var(--accent-line)"
        strokeWidth={1}
        opacity={0.4}
      />
      <line
        x1={xLo}
        y1={mid}
        x2={xHi}
        y2={mid}
        stroke="var(--ink-400)"
        strokeWidth={1}
      />
      {lo < scaleMin && (
        <polygon
          points={`${1},${mid} ${6},${mid - 3} ${6},${mid + 3}`}
          fill="var(--ink-400)"
        />
      )}
      {hi > scaleMax && (
        <polygon
          points={`${width - 1},${mid} ${width - 6},${mid - 3} ${width - 6},${mid + 3}`}
          fill="var(--ink-400)"
        />
      )}
      <circle cx={xPt} cy={mid} r={dotR} fill={dotColor} />
    </svg>
  );
}

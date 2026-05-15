"use client";

import { forestPlot as fp } from "@/lib/design-tokens";
import { logScale, logTicks } from "./log-scale";

export type ForestRow = {
  reaction: string;
  ror: number;
  lo: number;
  hi: number;
  n: number;
  prr: number;
  chi2: number;
  flagged: boolean;
};

function ForestAxis({
  plotX,
  plotW,
  y,
}: {
  plotX: number;
  plotW: number;
  y: number;
}) {
  const ticks = logTicks(fp.scaleMin, fp.scaleMax);
  return (
    <g>
      <line
        x1={plotX}
        y1={y}
        x2={plotX + plotW}
        y2={y}
        stroke="var(--ink-500)"
        strokeWidth={1}
      />
      {ticks.map((t) => {
        const x = plotX + logScale(t, fp.scaleMin, fp.scaleMax, plotW);
        return (
          <g key={t}>
            <line
              x1={x}
              y1={y}
              x2={x}
              y2={y + 5}
              stroke="var(--ink-500)"
              strokeWidth={1}
            />
            <text
              x={x}
              y={y + 16}
              textAnchor="middle"
              fill="var(--ink-400)"
              fontSize={10}
              fontFamily="var(--font-mono)"
            >
              {t}
            </text>
          </g>
        );
      })}
    </g>
  );
}

function ForestLegend({
  x,
  y,
  width,
}: {
  x: number;
  y: number;
  width: number;
}) {
  return (
    <g>
      <text
        x={x}
        y={y}
        fill="var(--ink-400)"
        fontSize={10}
        fontFamily="var(--font-mono)"
      >
        Figure 1 &middot; Forest plot &middot; ROR with 95% CI (log&#x2081;&#x2080;
        scale)
      </text>
      <text
        x={x}
        y={y + 14}
        fill="var(--ink-500)"
        fontSize={9}
        fontFamily="var(--font-body)"
      >
        Disproportionality analysis on FDA FAERS. Signal = ROR lower CI
        &gt; 1 + EVANS (PRR &ge; 2, n &ge; 3, &chi;&sup2; &ge; 4). Source:
        OpenFDA weekly snapshot.
      </text>
      <line
        x1={x}
        y1={y + 22}
        x2={x + width}
        y2={y + 22}
        stroke="var(--border-rule)"
        strokeWidth={1}
      />
    </g>
  );
}

export function ForestPlot({
  rows,
  width = fp.defaultWidth,
  leftCol = fp.leftCol,
  rightCol = fp.rightCol,
  rowH = fp.rowH,
  showEvans = true,
}: {
  rows: ForestRow[];
  width?: number;
  leftCol?: number;
  rightCol?: number;
  rowH?: number;
  showEvans?: boolean;
}) {
  const captionH = 36;
  const axisH = 24;
  const plotW = width - leftCol - rightCol;
  const bodyH = rows.length * rowH;
  const totalH = captionH + axisH + bodyH + 8;

  const nullX = leftCol + logScale(fp.nullLine, fp.scaleMin, fp.scaleMax, plotW);

  return (
    <svg
      width={width}
      height={totalH}
      className="select-none"
      style={{ fontFeatureSettings: '"tnum"' }}
    >
      {/* Caption */}
      <ForestLegend x={leftCol} y={10} width={plotW} />

      {/* Axis */}
      <ForestAxis plotX={leftCol} plotW={plotW} y={captionH} />

      {/* Null reference wash + line */}
      <rect
        x={nullX - 8}
        y={captionH + axisH}
        width={16}
        height={bodyH}
        fill={fp.nullWash}
      />
      <line
        x1={nullX}
        y1={captionH + axisH}
        x2={nullX}
        y2={captionH + axisH + bodyH}
        stroke={fp.nullLineColor}
        strokeWidth={1}
      />
      <text
        x={nullX}
        y={captionH + 4}
        textAnchor="middle"
        fill="var(--accent-muted)"
        fontSize={8}
        fontFamily="var(--font-mono)"
      >
        ROR = 1
      </text>

      {/* Column headers in right col */}
      <g>
        {(() => {
          const hy = captionH + axisH - 4;
          const cols = [
            { label: "ROR", dx: 0 },
            { label: "95% CI", dx: 55 },
            { label: "n", dx: 140 },
          ];
          if (showEvans) cols.push({ label: "EVANS", dx: 170 });
          return cols.map((c) => (
            <text
              key={c.label}
              x={leftCol + plotW + 10 + c.dx}
              y={hy}
              fill="var(--ink-500)"
              fontSize={9}
              fontFamily="var(--font-mono)"
            >
              {c.label}
            </text>
          ));
        })()}
      </g>

      {/* Rows */}
      {rows.map((row, i) => {
        const y = captionH + axisH + i * rowH + rowH / 2;
        const clampPt = Math.max(Math.min(row.ror, fp.scaleMax), fp.scaleMin);
        const xPt = leftCol + logScale(clampPt, fp.scaleMin, fp.scaleMax, plotW);

        const loExceeds = row.lo < fp.scaleMin;
        const hiExceeds = row.hi > fp.scaleMax;
        const clampLo = Math.max(row.lo, fp.scaleMin);
        const clampHi = Math.min(row.hi, fp.scaleMax);
        const xLo = leftCol + logScale(clampLo, fp.scaleMin, fp.scaleMax, plotW);
        const xHi = leftCol + logScale(clampHi, fp.scaleMin, fp.scaleMax, plotW);

        const dotR = row.flagged ? fp.flaggedDotR : fp.unflaggedDotR;
        const dotColor = row.flagged ? fp.flaggedColor : fp.unflaggedColor;

        const evansChecks = [row.n >= 3, row.prr >= 2, row.chi2 >= 4];

        return (
          <g key={row.reaction}>
            {/* Alternating row bg */}
            {i % 2 === 0 && (
              <rect
                x={0}
                y={y - rowH / 2}
                width={width}
                height={rowH}
                fill="rgba(255,255,255,0.015)"
              />
            )}

            {/* Reaction label */}
            <text
              x={leftCol - 8}
              y={y + 4}
              textAnchor="end"
              fill="var(--ink-200)"
              fontSize={11}
              fontFamily="var(--font-body)"
            >
              {row.reaction.length > 28
                ? row.reaction.slice(0, 26) + "…"
                : row.reaction}
            </text>

            {/* CI line */}
            <line
              x1={xLo}
              y1={y}
              x2={xHi}
              y2={y}
              stroke="var(--ink-400)"
              strokeWidth={1.5}
            />

            {/* Left arrow if lo exceeds */}
            {loExceeds && (
              <polygon
                points={`${leftCol + 1},${y} ${leftCol + 7},${y - 3.5} ${leftCol + 7},${y + 3.5}`}
                fill="var(--ink-400)"
              />
            )}

            {/* Right arrow if hi exceeds */}
            {hiExceeds && (
              <polygon
                points={`${leftCol + plotW - 1},${y} ${leftCol + plotW - 7},${y - 3.5} ${leftCol + plotW - 7},${y + 3.5}`}
                fill="var(--ink-400)"
              />
            )}

            {/* Flagged halo */}
            {row.flagged && (
              <circle
                cx={xPt}
                cy={y}
                r={dotR + 4}
                fill="none"
                stroke={fp.flaggedHalo}
                strokeWidth={1.5}
              />
            )}

            {/* Point estimate dot */}
            <circle cx={xPt} cy={y} r={dotR} fill={dotColor} />

            {/* Right-side numeric columns */}
            <text
              x={leftCol + plotW + 10}
              y={y + 4}
              fill={row.flagged ? "var(--accent)" : "var(--ink-300)"}
              fontSize={11}
              fontFamily="var(--font-mono)"
            >
              {row.ror.toFixed(2)}
            </text>
            <text
              x={leftCol + plotW + 65}
              y={y + 4}
              fill="var(--ink-400)"
              fontSize={10}
              fontFamily="var(--font-mono)"
            >
              {row.lo.toFixed(1)}–{row.hi > 999 ? ">999" : row.hi.toFixed(1)}
            </text>
            <text
              x={leftCol + plotW + 150}
              y={y + 4}
              fill="var(--ink-400)"
              fontSize={11}
              fontFamily="var(--font-mono)"
            >
              {row.n}
            </text>

            {/* EVANS glyph */}
            {showEvans &&
              evansChecks.map((pass, j) => (
                <rect
                  key={j}
                  x={leftCol + plotW + 180 + j * 10}
                  y={y - 4}
                  width={7}
                  height={7}
                  rx={0}
                  fill={pass ? "var(--accent)" : "var(--ink-600)"}
                />
              ))}
          </g>
        );
      })}
    </svg>
  );
}

import type { Witness } from "../types";

const WIDTH = 780;
const ROW_H = 32;
const PAD_X = 90;

function fmt(v: number): string {
  if (!Number.isFinite(v)) return String(v);
  const p = Number(v.toPrecision(6));
  return String(p);
}

/**
 * Per-witness band chart: one row for the common distance band plus one row
 * per channel showing that channel's feasible tooth interval.
 */
export function BandChart({ witness }: { witness: Witness }) {
  const rows = [
    {
      label: "共同距离带",
      lo: witness.interval.lo.approx,
      hi: witness.interval.hi.approx,
      kind: "common" as const,
    },
    ...witness.channels.map((c) => ({
      label: `第 ${c.index + 1} 路`,
      lo: c.band.lo.approx,
      hi: c.band.hi.approx,
      kind: "channel" as const,
    })),
  ];

  let v0 = Math.min(...rows.map((r) => r.lo));
  let v1 = Math.max(...rows.map((r) => r.hi));
  if (!(v1 > v0)) {
    v0 -= 0.5;
    v1 += 0.5;
  }
  const margin = (v1 - v0) * 0.05;
  v0 -= margin;
  v1 += margin;

  const x = (v: number) => PAD_X + ((v - v0) / (v1 - v0)) * (WIDTH - PAD_X - 16);
  const height = rows.length * ROW_H + 30;
  const commonLo = witness.interval.lo.approx;
  const commonHi = witness.interval.hi.approx;
  const ticks = [v0, commonLo, commonHi, v1].filter(
    (v, i, arr) => arr.findIndex((u) => Math.abs(u - v) < (v1 - v0) * 1e-9) === i,
  );

  return (
    <svg
      className="band-chart"
      viewBox={`0 0 ${WIDTH} ${height}`}
      role="img"
      aria-label="共同距离带与各通道可行带"
    >
      {ticks.map((t, i) => (
        <g key={i}>
          <line className="grid-line" x1={x(t)} x2={x(t)} y1={0} y2={height - 22} />
          <text className="tick-label" x={x(t)} y={height - 8} textAnchor="middle">
            {fmt(t)}
          </text>
        </g>
      ))}
      {rows.map((row, i) => {
        const y = i * ROW_H + 6;
        const x0 = x(row.lo);
        const x1 = Math.max(x(row.hi), x0 + 2);
        return (
          <g key={i}>
            <text className="row-label" x={PAD_X - 8} y={y + 14} textAnchor="end">
              {row.label}
            </text>
            <line className="row-axis" x1={PAD_X} x2={WIDTH - 16} y1={y + 10} y2={y + 10} />
            <rect
              className={row.kind === "common" ? "band-common" : "band-channel"}
              x={x0}
              y={y + 2}
              width={x1 - x0}
              height={16}
              rx={3}
            >
              <title>{`${row.label} ∈ [${fmt(row.lo)}, ${fmt(row.hi)}]`}</title>
            </rect>
          </g>
        );
      })}
    </svg>
  );
}

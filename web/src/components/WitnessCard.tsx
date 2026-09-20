import type { ExactNum, Witness } from "../types";
import { BandChart } from "./BandChart";

function Num({ value }: { value: ExactNum }) {
  return (
    <span className="num" title={`≈ ${value.approx}`}>
      {value.exact}
    </span>
  );
}

function Approx({ value }: { value: ExactNum }) {
  return <span className="approx">≈ {Number(value.approx.toPrecision(8))}</span>;
}

/** One possibility class: integer vector, common distance band, per-channel detail. */
export function WitnessCard({ witness, index }: { witness: Witness; index: number }) {
  return (
    <section className="witness-card" data-testid={`witness-${index}`}>
      <header className="witness-header">
        <h3>见证 #{index + 1}</h3>
        <div className="vector-chips">
          {witness.integers.map((n, i) => (
            <span className="chip" key={i} data-testid={`integer-${index}-${i}`}>
              n<sub>{i + 1}</sub>={n}
            </span>
          ))}
        </div>
      </header>

      <p className="common-band">
        共同距离带：d ∈ [<Num value={witness.interval.lo} />,{" "}
        <Num value={witness.interval.hi} />]{" "}
        <span className="approx-pair">
          （<Approx value={witness.interval.lo} />, <Approx value={witness.interval.hi} />）
        </span>
      </p>

      <table className="detail-table">
        <thead>
          <tr>
            <th>通道</th>
            <th>整周数 n</th>
            <th>通道距离带（精确）</th>
            <th>残差区间（精确）</th>
          </tr>
        </thead>
        <tbody>
          {witness.channels.map((c) => (
            <tr key={c.index} data-testid={`witness-${index}-channel-${c.index}`}>
              <td>第 {c.index + 1} 路</td>
              <td className="mono">{c.integer}</td>
              <td className="mono">
                [<Num value={c.band.lo} />, <Num value={c.band.hi} />]
              </td>
              <td className="mono">
                [<Num value={c.residual.lo} />, <Num value={c.residual.hi} />]
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <BandChart witness={witness} />
    </section>
  );
}

import React from "react";

function Exact({ q }) {
  if (!q) return null;
  return (
    <span className="exact" title={q.exact ? "有限十进制，精确值" : "十进制为近似，分数为精确值"}>
      <span className="decimal">{q.decimal}</span>
      <span className="fraction">{q.fraction}</span>
      {q.exact ? null : <span className="approx">≈</span>}
    </span>
  );
}

export default function WitnessCard({ witness, channelCount }) {
  const band = witness.distance_band;
  return (
    <section className={`witness ${witness.verified ? "verified" : "failed"}`}>
      <header>
        <h4>候选见证 #{witness.rank}</h4>
        <span className={`badge ${witness.verified ? "ok" : "bad"}`}>
          {witness.verified ? "逐路复核通过" : "复核未通过"}
        </span>
      </header>

      <div className="band">
        <div className="band-label">共同距离带（精确交集）</div>
        <div className="band-values">
          <Exact q={band.lower} />
          <span className="sep">≤ d ≤</span>
          <Exact q={band.upper} />
        </div>
        <div className="band-width">
          带宽 <Exact q={band.width} />
        </div>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>波长 λ</th>
              <th>包裹相位 p</th>
              <th>误差界 ε</th>
              <th>整周数 n</th>
              <th>残差区间（周）</th>
              <th>|d/λ−n−p| ≤ ε</th>
            </tr>
          </thead>
          <tbody>
            {witness.per_channel.map((row) => (
              <tr key={row.index}>
                <td className="idx">{row.index + 1}</td>
                <td><Exact q={row.wavelength} /></td>
                <td><Exact q={row.phase} /></td>
                <td><Exact q={row.epsilon} /></td>
                <td className="order" title={String(row.order)}>
                  {Number(row.order).toLocaleString("en-US")}
                </td>
                <td>
                  [ <Exact q={row.residual_lower} /> ;{" "}
                  <Exact q={row.residual_upper} /> ]
                </td>
                <td>
                  <span className={`badge ${row.within_tolerance ? "ok" : "bad"}`}>
                    {row.within_tolerance ? "满足" : "越界"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

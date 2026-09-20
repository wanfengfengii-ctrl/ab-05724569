import React from "react";
import WitnessCard from "./WitnessCard.jsx";

function formatInt(n) {
  return Number(n).toLocaleString("zh-CN");
}

export default function ResultsPanel({ result, error, loading }) {
  if (loading) {
    return (
      <div className="results" data-testid="results">
        <div className="status loading">正在以精确有理数解算全部整周类别…</div>
      </div>
    );
  }
  if (error) {
    return (
      <div className="results" data-testid="results">
        <div className="status error">
          <strong>解算请求失败：</strong>
          <pre>{error.messages?.join("\n") ?? String(error.message ?? error)}</pre>
        </div>
      </div>
    );
  }
  if (!result) {
    return (
      <div className="results" data-testid="results">
        <div className="status empty">
          尚未解算。请在左侧填写或导入距离闭区间与 2–32 路读数，然后点击「发起精确解算」。
          任何输入变化都会使此处结论立即作废。
        </div>
      </div>
    );
  }

  const { stats } = result;
  return (
    <div className="results" data-testid="results">
      <div className={`verdict ${result.status}`}>
        <div className="verdict-title">
          {result.status === "unique" && "裁决：唯一可行整周向量"}
          {result.status === "multiple" &&
            `裁决：存在 ${formatInt(result.total_solutions)} 个可行类别（候选不唯一）`}
          {result.status === "infeasible" && "裁决：无解"}
        </div>
        <p className="verdict-text">{result.verdict}</p>
      </div>

      <div className="stats">
        <span>通道数：{stats.channels}</span>
        <span title="分支限界实际细化的候选整数格 / 两路重合簇数">
          实际细化分支：<strong>{formatInt(stats.cells_refined)}</strong>
        </span>
        <span title="逐一枚举最短波长覆盖量程所需的整周数（本系统不会这样做）">
          若按最短波长逐个枚举：<strong>{formatInt(stats.naive_shortest_wavelength_integers)}</strong>
        </span>
      </div>

      {result.status === "infeasible" ? (
        <div className="infeasible-box">
          在给定闭区间与每路误差界内，不存在任何整周向量同时满足
          <code> |d/λ − n − p| ≤ ε</code>。可能原因：读数互相矛盾、相位解算错误、
          粗测区间错误或误差界过紧。
        </div>
      ) : (
        result.witnesses.map((w) => (
          <WitnessCard key={w.rank} witness={w} />
        ))
      )}

      {result.status === "multiple" && (
        <p className="more-hint">
          仅展示按交集下端点、整周向量字典序排序的前两份见证；共{" "}
          {formatInt(result.total_solutions)} 类。
        </p>
      )}
    </div>
  );
}

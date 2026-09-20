import { useEffect, useMemo, useRef, useState } from "react";
import { solve } from "./api";
import { DEFAULT_STATE, PRESETS } from "./presets";
import type { InputState } from "./validation";
import { validateInputs } from "./validation";
import type { SolveResponse } from "./types";
import { WitnessCard } from "./components/WitnessCard";

function parseImport(text: string): InputState {
  const data = JSON.parse(text) as {
    range?: { lo?: unknown; hi?: unknown };
    channels?: unknown;
  };
  const toStr = (v: unknown, field: string): string => {
    if (typeof v === "number" || typeof v === "string") return String(v);
    throw new Error(`字段 ${field} 必须是十进制数或字符串`);
  };
  if (!data || typeof data !== "object") throw new Error("导入内容必须是 JSON 对象");
  if (!data.range) throw new Error("缺少 range 字段");
  if (!Array.isArray(data.channels)) throw new Error("缺少 channels 数组");
  return {
    lo: toStr(data.range.lo, "range.lo"),
    hi: toStr(data.range.hi, "range.hi"),
    channels: data.channels.map((c, i) => {
      const ch = c as Record<string, unknown>;
      return {
        wavelength: toStr(ch.wavelength, `channels[${i}].wavelength`),
        phase: toStr(ch.phase, `channels[${i}].phase`),
        epsilon: toStr(ch.epsilon, `channels[${i}].epsilon`),
      };
    }),
  };
}

const STATUS_TEXT: Record<SolveResponse["status"], string> = {
  unique: "唯一解：仅存在一个满足全部通道的整周向量",
  multiple: "多解：按交集下端点与整周向量字典序展示前两份见证",
  none: "无解：给定区间内不存在满足全部通道约束的整周向量",
};

export default function App() {
  const [state, setState] = useState<InputState>(DEFAULT_STATE);
  const [result, setResult] = useState<SolveResponse | null>(null);
  const [solveError, setSolveError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [importText, setImportText] = useState("");
  const [importError, setImportError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Any input change invalidates previous conclusions immediately.
  const fingerprint = useMemo(() => JSON.stringify(state), [state]);
  useEffect(() => {
    setResult(null);
    setSolveError(null);
  }, [fingerprint]);

  const errors = validateInputs(state);

  const updateChannel = (index: number, field: keyof InputState["channels"][number], value: string) => {
    setState((s) => ({
      ...s,
      channels: s.channels.map((c, i) => (i === index ? { ...c, [field]: value } : c)),
    }));
  };

  const addChannel = () => {
    setState((s) =>
      s.channels.length >= 32
        ? s
        : { ...s, channels: [...s.channels, { wavelength: "1", phase: "0", epsilon: "0.05" }] },
    );
  };

  const removeChannel = (index: number) => {
    setState((s) =>
      s.channels.length <= 1 ? s : { ...s, channels: s.channels.filter((_, i) => i !== index) },
    );
  };

  const applyPreset = (key: string) => {
    const preset = PRESETS.find((p) => p.key === key);
    if (preset) setState(preset.state);
  };

  const doSolve = async () => {
    setLoading(true);
    try {
      const resp = await solve({
        range: { lo: state.lo.trim(), hi: state.hi.trim() },
        channels: state.channels.map((c) => ({
          wavelength: c.wavelength.trim(),
          phase: c.phase.trim(),
          epsilon: c.epsilon.trim(),
        })),
      });
      setResult(resp);
      setSolveError(null);
    } catch (err) {
      setResult(null);
      setSolveError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const applyImport = (text: string) => {
    try {
      setState(parseImport(text));
      setImportError(null);
      setShowImport(false);
      setImportText("");
    } catch (err) {
      setImportError(err instanceof Error ? err.message : String(err));
    }
  };

  const onImportFile = (file: File) => {
    file.text().then(
      (text) => applyImport(text),
      () => setImportError("读取文件失败"),
    );
  };

  const doExport = () => {
    const payload = {
      range: { lo: state.lo, hi: state.hi },
      channels: state.channels,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "interferometry-input.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="page">
      <header className="page-header">
        <h1>多波长激光干涉仪 · 整周数解算工作台</h1>
        <p>
          每路读数只给出包裹相位，整周数未知。本工作台以<strong>精确有理数</strong>
          求解满足 |d/λ − n − p| ≤ ε 的全部整周向量类别，并给出共同距离带。
        </p>
      </header>

      <section className="card">
        <h2>测量输入</h2>
        <div className="range-row">
          <label htmlFor="range-lo">距离闭区间 lo</label>
          <input
            id="range-lo"
            data-testid="range-lo"
            value={state.lo}
            onChange={(e) => setState((s) => ({ ...s, lo: e.target.value }))}
          />
          <label htmlFor="range-hi">hi</label>
          <input
            id="range-hi"
            data-testid="range-hi"
            value={state.hi}
            onChange={(e) => setState((s) => ({ ...s, hi: e.target.value }))}
          />
        </div>

        <table className="channel-table">
          <thead>
            <tr>
              <th>通道</th>
              <th>波长 λ（&gt; 0）</th>
              <th>相位 p（0 ≤ p &lt; 1）</th>
              <th>误差界 ε（&lt; 1/4）</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {state.channels.map((c, i) => (
              <tr key={i} data-testid={`channel-row-${i}`}>
                <td>第 {i + 1} 路</td>
                <td>
                  <input
                    data-testid={`input-wavelength-${i}`}
                    value={c.wavelength}
                    onChange={(e) => updateChannel(i, "wavelength", e.target.value)}
                  />
                </td>
                <td>
                  <input
                    data-testid={`input-phase-${i}`}
                    value={c.phase}
                    onChange={(e) => updateChannel(i, "phase", e.target.value)}
                  />
                </td>
                <td>
                  <input
                    data-testid={`input-epsilon-${i}`}
                    value={c.epsilon}
                    onChange={(e) => updateChannel(i, "epsilon", e.target.value)}
                  />
                </td>
                <td>
                  <button
                    type="button"
                    className="link-button"
                    data-testid={`remove-channel-${i}`}
                    onClick={() => removeChannel(i)}
                    disabled={state.channels.length <= 1}
                  >
                    删除
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="toolbar">
          <button type="button" data-testid="add-channel" onClick={addChannel} disabled={state.channels.length >= 32}>
            添加通道（{state.channels.length}/32）
          </button>
          <button type="button" data-testid="import-toggle" onClick={() => setShowImport((v) => !v)}>
            导入 JSON
          </button>
          <button type="button" data-testid="export-button" onClick={doExport}>
            导出 JSON
          </button>
          {PRESETS.map((p) => (
            <button type="button" key={p.key} data-testid={`preset-${p.key}`} onClick={() => applyPreset(p.key)}>
              {p.label}
            </button>
          ))}
        </div>

        {showImport && (
          <div className="import-panel">
            <textarea
              data-testid="import-textarea"
              placeholder='粘贴 {"range":{"lo":"0","hi":"10"},"channels":[{"wavelength":"2","phase":"0.5","epsilon":"0.1"},…]}'
              value={importText}
              onChange={(e) => setImportText(e.target.value)}
              rows={5}
            />
            <div className="toolbar">
              <button type="button" data-testid="import-apply" onClick={() => applyImport(importText)}>
                应用导入
              </button>
              <button type="button" data-testid="import-file" onClick={() => fileInputRef.current?.click()}>
                选择文件…
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept="application/json,.json"
                hidden
                data-testid="import-file-input"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) onImportFile(f);
                  e.target.value = "";
                }}
              />
            </div>
            {importError && <p className="error-text" data-testid="import-error">{importError}</p>}
          </div>
        )}

        {errors.length > 0 && (
          <ul className="error-list" data-testid="validation-errors">
            {errors.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        )}

        <div className="solve-row">
          <button
            type="button"
            className="solve-button"
            data-testid="solve-button"
            disabled={loading || errors.length > 0}
            onClick={doSolve}
          >
            {loading ? "解算中…" : "解算"}
          </button>
        </div>
      </section>

      {solveError && (
        <div className="banner banner-error" data-testid="solve-error">
          解算失败：{solveError}
        </div>
      )}

      {result && (
        <section className="result" data-testid="result">
          <div className={`banner banner-${result.status}`} data-testid="status-banner">
            {STATUS_TEXT[result.status]}
            {result.status === "multiple" && <strong>（共 {result.total_classes} 类）</strong>}
          </div>
          <p className="result-meta" data-testid="result-meta">
            解算模式：{result.mode === "periodic" ? "周期合并（CRT）" : "增量求精"} · 考察候选{" "}
            {result.candidates_examined} · 耗时 {result.elapsed_ms} ms · 可能性类别总数{" "}
            {result.total_classes}
          </p>
          {result.witnesses.map((w, i) => (
            <WitnessCard key={i} witness={w} index={i} />
          ))}
        </section>
      )}
    </div>
  );
}

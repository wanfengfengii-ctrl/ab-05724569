import React, { useEffect, useMemo, useRef, useState } from "react";
import { apiExamples, apiHealth, apiSolve } from "./api.js";
import { validateModel } from "./validation.js";
import InputEditor from "./components/InputEditor.jsx";
import ResultsPanel from "./components/ResultsPanel.jsx";

const DEFAULT_MODEL = {
  distance: { min: "0", max: "1.2" },
  channels: [
    { wavelength: "1", phase: "0.25", epsilon: "0.1" },
    { wavelength: "1", phase: "0.35", epsilon: "0.1" },
  ],
};

function normalizeImport(raw) {
  if (!raw || typeof raw !== "object") throw new Error("JSON 顶层必须是对象");
  const { distance, channels } = raw;
  if (!distance || typeof distance.min !== "string" || typeof distance.max !== "string")
    throw new Error('需要形如 {"distance":{"min":"…","max":"…"}} 的距离闭区间');
  if (!Array.isArray(channels) || channels.length < 2 || channels.length > 32)
    throw new Error("channels 必须是含 2–32 个元素的数组");
  const norm = channels.map((c, i) => {
    if (!c || ["wavelength", "phase", "epsilon"].some((k) => typeof c[k] !== "string"))
      throw new Error(`第 ${i + 1} 路必须含字符串字段 wavelength / phase / epsilon`);
    return { wavelength: c.wavelength, phase: c.phase, epsilon: c.epsilon };
  });
  return { distance: { min: distance.min, max: distance.max }, channels: norm };
}

export default function App() {
  const [model, setModelState] = useState(DEFAULT_MODEL);
  const [result, setResult] = useState(null);
  const [apiError, setApiError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [examples, setExamples] = useState([]);
  const [health, setHealth] = useState("checking");
  const [importOpen, setImportOpen] = useState(false);
  const [importText, setImportText] = useState("");
  const [importErr, setImportErr] = useState(null);
  const seqRef = useRef(0);
  const fileRef = useRef(null);

  // 任何输入变化都不得保留旧结论：统一经此函数修改模型。
  const setModel = (updater) => {
    seqRef.current += 1; // 令一切在途解算响应立即过期
    setModelState(updater);
    setResult(null);
    setApiError(null);
  };

  useEffect(() => {
    apiHealth()
      .then(() => setHealth("ok"))
      .catch(() => setHealth("down"));
    apiExamples().then(setExamples).catch(() => setExamples([]));
  }, []);

  const clientErrors = useMemo(() => validateModel(model), [model]);

  const solve = async () => {
    if (clientErrors.length > 0) return;
    const seq = seqRef.current + 1;
    seqRef.current = seq;
    setLoading(true);
    setApiError(null);
    setResult(null);
    try {
      const body = await apiSolve(model);
      // 迟到的响应（用户已改输入）不得覆盖当前视图。
      if (seqRef.current === seq) setResult(body);
    } catch (e) {
      if (seqRef.current === seq) setApiError(e);
    } finally {
      if (seqRef.current === seq) setLoading(false);
    }
  };

  const loadExample = (id) => {
    const ex = examples.find((e) => e.id === id);
    if (ex) setModel(() => ex.input);
  };

  const exportJson = () => {
    const blob = new Blob([JSON.stringify(model, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "interferometer-input.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  const onPickFile = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        setImportErr(null);
        const parsed = normalizeImport(JSON.parse(String(reader.result)));
        setModel(() => parsed);
        setImportOpen(false);
        setImportText("");
      } catch (err) {
        setImportErr(err.message);
      }
    };
    reader.readAsText(file);
    e.target.value = "";
  };

  const onImportPaste = () => {
    try {
      setImportErr(null);
      const parsed = normalizeImport(JSON.parse(importText));
      setModel(() => parsed);
      setImportOpen(false);
      setImportText("");
    } catch (err) {
      setImportErr(err.message);
    }
  };

  return (
    <div className="app">
      <header className="topbar">
        <div>
          <h1>多波长激光干涉 · 整周解算工作台</h1>
          <p className="subtitle">
            精确有理数裁决 · 分支限界 + 合成波长模跳变，不枚举最短波长整周
          </p>
        </div>
        <div className={`health health-${health}`} data-testid="health">
          {health === "ok" && "● API 在线"}
          {health === "down" && "● API 不可达"}
          {health === "checking" && "● 检查 API…"}
        </div>
      </header>

      <div className="toolbar">
        <label className="example-pick">
          载入示例：
          <select onChange={(e) => e.target.value && loadExample(e.target.value)} defaultValue="">
            <option value="" disabled>
              选择场景…
            </option>
            {examples.map((ex) => (
              <option key={ex.id} value={ex.id}>
                {ex.title}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="btn secondary" onClick={() => setImportOpen(true)}>
          导入 JSON
        </button>
        <button type="button" className="btn secondary" onClick={exportJson}>
          导出 JSON
        </button>
        <button
          type="button"
          className="btn primary"
          onClick={solve}
          disabled={loading || clientErrors.length > 0}
          data-testid="solve-btn"
        >
          {loading ? "解算中…" : "发起精确解算"}
        </button>
      </div>

      <main className="layout">
        <section className="pane input-pane">
          <InputEditor
            model={model}
            setModel={setModel}
            errors={clientErrors}
            disabled={loading}
          />
          {clientErrors.length > 0 && (
            <div className="client-errors" data-testid="client-errors">
              {clientErrors.map((e, i) => (
                <div key={i}>· {e.msg}</div>
              ))}
            </div>
          )}
        </section>
        <section className="pane result-pane">
          <ResultsPanel result={result} error={apiError} loading={loading} />
        </section>
      </main>

      {importOpen && (
        <div className="modal-backdrop" onClick={() => setImportOpen(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>导入读数</h3>
            <p>
              选择 JSON 文件，或直接粘贴。结构：
              <code>{'{"distance":{"min":"0","max":"1.2"},"channels":[{"wavelength":"1","phase":"0.25","epsilon":"0.1"}]}'}</code>
            </p>
            <input ref={fileRef} type="file" accept="application/json,.json" onChange={onPickFile} />
            <textarea
              rows={8}
              value={importText}
              placeholder='{"distance":{…},"channels":[…]}'
              onChange={(e) => setImportText(e.target.value)}
            />
            {importErr && <div className="field-error">{importErr}</div>}
            <div className="modal-actions">
              <button type="button" className="btn secondary" onClick={() => setImportOpen(false)}>
                取消
              </button>
              <button
                type="button"
                className="btn primary"
                onClick={onImportPaste}
                disabled={!importText.trim()}
              >
                导入粘贴内容
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

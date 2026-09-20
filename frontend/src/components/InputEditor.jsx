import React from "react";

function FieldError({ msg }) {
  return msg ? <div className="field-error">{msg}</div> : null;
}

export default function InputEditor({ model, setModel, errors, disabled }) {
  const em = new Map(errors.map((e) => [e.path, e.msg]));

  const setDistance = (key, value) =>
    setModel((m) => ({ ...m, distance: { ...m.distance, [key]: value } }));

  const setChannel = (i, key, value) =>
    setModel((m) => ({
      ...m,
      channels: m.channels.map((c, j) => (j === i ? { ...c, [key]: value } : c)),
    }));

  const addChannel = () =>
    setModel((m) =>
      m.channels.length >= 32
        ? m
        : {
            ...m,
            channels: [
              ...m.channels,
              { wavelength: "1", phase: "0", epsilon: "0.01" },
            ],
          }
        );

  const removeChannel = (i) =>
    setModel((m) => ({
      ...m,
      channels: m.channels.filter((_, j) => j !== i),
    }));

  const cls = (path) => (em.has(path) ? "invalid" : "");

  return (
    <div className="editor">
      <fieldset className="distance-box">
        <legend>距离闭区间（长度单位与波长一致）</legend>
        <label>
          下端点
          <input
            className={cls("distance.min")}
            value={model.distance.min}
            disabled={disabled}
            onChange={(e) => setDistance("min", e.target.value)}
            inputMode="decimal"
            data-testid="distance-min"
          />
        </label>
        <span className="interval-sep">≤ d ≤</span>
        <label>
          上端点
          <input
            className={cls("distance.max")}
            value={model.distance.max}
            disabled={disabled}
            onChange={(e) => setDistance("max", e.target.value)}
            inputMode="decimal"
            data-testid="distance-max"
          />
        </label>
        <FieldError msg={em.get("distance.min") || em.get("distance.max") || em.get("distance")} />
      </fieldset>

      <div className="channels-head">
        <h3>波长通道（{model.channels.length} 路，允许 2–32）</h3>
        <button
          type="button"
          className="btn secondary"
          onClick={addChannel}
          disabled={disabled || model.channels.length >= 32}
        >
          + 增加一路
        </button>
      </div>

      <div className="table-wrap">
        <table className="channel-table">
          <thead>
            <tr>
              <th>#</th>
              <th>波长 λ（&gt;0）</th>
              <th>包裹相位 p（[0,1)）</th>
              <th>误差界 ε（&lt;1/4 周）</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {model.channels.map((c, i) => (
              <React.Fragment key={i}>
                <tr>
                  <td className="idx">{i + 1}</td>
                  <td>
                    <input
                      className={cls(`channels.${i}.wavelength`)}
                      value={c.wavelength}
                      disabled={disabled}
                      onChange={(e) => setChannel(i, "wavelength", e.target.value)}
                      inputMode="decimal"
                      aria-label={`第 ${i + 1} 路波长`}
                    />
                  </td>
                  <td>
                    <input
                      className={cls(`channels.${i}.phase`)}
                      value={c.phase}
                      disabled={disabled}
                      onChange={(e) => setChannel(i, "phase", e.target.value)}
                      inputMode="decimal"
                      aria-label={`第 ${i + 1} 路相位`}
                    />
                  </td>
                  <td>
                    <input
                      className={cls(`channels.${i}.epsilon`)}
                      value={c.epsilon}
                      disabled={disabled}
                      onChange={(e) => setChannel(i, "epsilon", e.target.value)}
                      inputMode="decimal"
                      aria-label={`第 ${i + 1} 路误差界`}
                    />
                  </td>
                  <td>
                    <button
                      type="button"
                      className="btn ghost danger"
                      disabled={disabled || model.channels.length <= 2}
                      onClick={() => removeChannel(i)}
                      title="删除该路"
                    >
                      删除
                    </button>
                  </td>
                </tr>
                {(em.get(`channels.${i}.wavelength`) ||
                  em.get(`channels.${i}.phase`) ||
                  em.get(`channels.${i}.epsilon`)) && (
                  <tr className="error-row">
                    <td></td>
                    <td colSpan={4}>
                      <FieldError
                        msg={
                          em.get(`channels.${i}.wavelength`) ||
                          em.get(`channels.${i}.phase`) ||
                          em.get(`channels.${i}.epsilon`)
                        }
                      />
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>
      <FieldError msg={em.get("channels")} />
    </div>
  );
}

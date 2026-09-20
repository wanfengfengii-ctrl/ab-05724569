// 与后端相同的"有限十进制数"判定：拒绝浮点尾数、NaN、Infinity、分数等。
const DECIMAL_RE = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/;

export function isFiniteDecimal(s) {
  return typeof s === "string" && DECIMAL_RE.test(s.trim());
}

// 用字符串精确比较有限十进制数的正负/大小（避免 Number 丢精度）。
export function decimalSign(s) {
  if (!isFiniteDecimal(s)) return null;
  const n = Number(s.trim()); // 仅用于符号；输入长度可控，符号不丢
  if (n === 0) return 0;
  return n > 0 ? 1 : -1;
}

export function decimalCmp(a, b) {
  if (!isFiniteDecimal(a) || !isFiniteDecimal(b)) return null;
  const x = Number(a.trim());
  const y = Number(b.trim());
  if (x < y) return -1;
  if (x > y) return 1;
  return 0;
}

export function validateModel(model) {
  const errors = [];
  const loc = (path) => path.join(".");

  if (!isFiniteDecimal(model.distance.min))
    errors.push({ path: loc(["distance", "min"]), msg: "距离下端点必须是有限十进制数" });
  if (!isFiniteDecimal(model.distance.max))
    errors.push({ path: loc(["distance", "max"]), msg: "距离上端点必须是有限十进制数" });

  if (decimalSign(model.distance.min) === -1)
    errors.push({ path: loc(["distance", "min"]), msg: "距离不能为负" });
  const cmp = decimalCmp(model.distance.min, model.distance.max);
  if (cmp === 1)
    errors.push({ path: loc(["distance"]), msg: "距离闭区间要求 下端点 ≤ 上端点" });

  const n = model.channels.length;
  if (n < 2 || n > 32)
    errors.push({ path: loc(["channels"]), msg: "波长通道数必须在 2 到 32 之间" });

  model.channels.forEach((c, i) => {
    if (!isFiniteDecimal(c.wavelength))
      errors.push({ path: loc(["channels", i, "wavelength"]), msg: "波长必须是有限十进制数" });
    else if (decimalSign(c.wavelength) !== 1)
      errors.push({ path: loc(["channels", i, "wavelength"]), msg: "波长必须为正数" });

    if (!isFiniteDecimal(c.phase))
      errors.push({ path: loc(["channels", i, "phase"]), msg: "相位必须是有限十进制数" });
    else {
      const p = Number(c.phase.trim());
      if (p < 0 || p >= 1)
        errors.push({ path: loc(["channels", i, "phase"]), msg: "相位必须位于 [0, 1)" });
    }

    if (!isFiniteDecimal(c.epsilon))
      errors.push({ path: loc(["channels", i, "epsilon"]), msg: "误差界必须是有限十进制数" });
    else {
      const e = Number(c.epsilon.trim());
      if (e < 0 || e >= 0.25)
        errors.push({
          path: loc(["channels", i, "epsilon"]),
          msg: "误差界必须满足 0 ≤ ε < 1/4 周",
        });
    }
  });

  return errors;
}

export function errorMap(errors) {
  const m = new Map();
  for (const e of errors) {
    if (!m.has(e.path)) m.set(e.path, e.msg);
  }
  return m;
}

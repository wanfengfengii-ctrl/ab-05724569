import type { ChannelSpec } from "./types";

export const DECIMAL_RE = /^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$/;

export function isFiniteDecimal(s: string): boolean {
  return DECIMAL_RE.test(s.trim());
}

export interface InputState {
  lo: string;
  hi: string;
  channels: ChannelSpec[];
}

/** Client-side mirror of the backend validation rules (backend stays authoritative). */
export function validateInputs(state: InputState): string[] {
  const errors: string[] = [];
  const loOk = isFiniteDecimal(state.lo);
  const hiOk = isFiniteDecimal(state.hi);
  if (!loOk) errors.push("距离区间下端点不是有限十进制数");
  if (!hiOk) errors.push("距离区间上端点不是有限十进制数");
  if (loOk && hiOk && Number(state.lo) > Number(state.hi)) {
    errors.push("距离区间下端点不能大于上端点");
  }
  if (state.channels.length < 2) errors.push("至少需要 2 路通道");
  if (state.channels.length > 32) errors.push("最多支持 32 路通道");
  state.channels.forEach((c, i) => {
    const label = `第 ${i + 1} 路`;
    if (!isFiniteDecimal(c.wavelength)) {
      errors.push(`${label}：波长不是有限十进制数`);
    } else if (Number(c.wavelength) <= 0) {
      errors.push(`${label}：波长必须为正数`);
    }
    if (!isFiniteDecimal(c.phase)) {
      errors.push(`${label}：相位不是有限十进制数`);
    } else if (!(Number(c.phase) >= 0 && Number(c.phase) < 1)) {
      errors.push(`${label}：相位须满足 0 ≤ p < 1`);
    }
    if (!isFiniteDecimal(c.epsilon)) {
      errors.push(`${label}：误差界不是有限十进制数`);
    } else if (!(Number(c.epsilon) >= 0 && Number(c.epsilon) < 0.25)) {
      errors.push(`${label}：误差界须满足 0 ≤ ε < 1/4 周`);
    }
  });
  return errors;
}

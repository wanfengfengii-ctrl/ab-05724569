import type { InputState } from "./validation";

export interface Preset {
  key: string;
  label: string;
  state: InputState;
}

export const PRESETS: Preset[] = [
  {
    key: "unique",
    label: "示例：唯一解",
    state: {
      lo: "0",
      hi: "4",
      channels: [
        { wavelength: "2", phase: "0.5", epsilon: "0.05" },
        { wavelength: "3", phase: "0.3", epsilon: "0.05" },
      ],
    },
  },
  {
    key: "multiple",
    label: "示例：多解",
    state: {
      lo: "0",
      hi: "10",
      channels: [
        { wavelength: "2", phase: "0.5", epsilon: "0.1" },
        { wavelength: "3", phase: "0.25", epsilon: "0.1" },
      ],
    },
  },
  {
    key: "none",
    label: "示例：无解",
    state: {
      lo: "0",
      hi: "4",
      channels: [
        { wavelength: "2", phase: "0.5", epsilon: "0.05" },
        { wavelength: "3", phase: "0.5", epsilon: "0.05" },
      ],
    },
  },
  {
    key: "long-range",
    label: "示例：长距离（10⁹ 量程）",
    state: {
      lo: "0",
      hi: "1000000000",
      channels: [
        { wavelength: "1000", phase: "0", epsilon: "0.01" },
        { wavelength: "1001", phase: "0", epsilon: "0.01" },
      ],
    },
  },
];

export const DEFAULT_STATE: InputState = PRESETS[0].state;

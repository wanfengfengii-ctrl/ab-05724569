/** API contract types (mirrors the FastAPI backend). */

export interface ExactNum {
  /** Exact rational value: an integer or "numerator/denominator". */
  exact: string;
  /** Floating-point approximation for display/geometry. */
  approx: number;
}

export interface ChannelSpec {
  wavelength: string;
  phase: string;
  epsilon: string;
}

export interface SolveRequest {
  range: { lo: string; hi: string };
  channels: ChannelSpec[];
}

export interface WitnessChannel {
  index: number;
  integer: number;
  band: { lo: ExactNum; hi: ExactNum };
  residual: { lo: ExactNum; hi: ExactNum };
}

export interface Witness {
  integers: number[];
  interval: { lo: ExactNum; hi: ExactNum };
  channels: WitnessChannel[];
}

export type SolveStatus = "unique" | "multiple" | "none";

export interface SolveResponse {
  status: SolveStatus;
  total_classes: number;
  mode: "incremental" | "periodic";
  candidates_examined: number;
  elapsed_ms: number;
  range: { lo: ExactNum; hi: ExactNum };
  channels: { index: number; wavelength: ExactNum; phase: ExactNum; epsilon: ExactNum }[];
  witnesses: Witness[];
}

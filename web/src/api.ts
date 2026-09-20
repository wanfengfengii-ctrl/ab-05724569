import type { SolveRequest, SolveResponse } from "./types";

/** POST /api/solve with exact decimal strings. */
export async function solve(req: SolveRequest): Promise<SolveResponse> {
  const resp = await fetch("/api/solve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  const text = await resp.text();
  let body: unknown = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    /* fall through to the error path */
  }
  if (!resp.ok) {
    throw new Error(extractError(body) ?? `请求失败（HTTP ${resp.status}）`);
  }
  return body as SolveResponse;
}

function extractError(body: unknown): string | null {
  if (body == null || typeof body !== "object") return null;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        if (d && typeof d === "object" && "msg" in d) return String((d as { msg: unknown }).msg);
        return JSON.stringify(d);
      })
      .join("；");
  }
  return null;
}

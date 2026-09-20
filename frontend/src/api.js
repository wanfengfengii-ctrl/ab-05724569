// 后端 API 客户端：所有数值字段始终以字符串传输，由 Python Fraction 精确解析。
const API_BASE = "";

async function parseResponse(resp) {
  let body = null;
  try {
    body = await resp.json();
  } catch {
    /* 非 JSON（如网关错误） */
  }
  if (!resp.ok) {
    const detail = body?.detail;
    let messages;
    if (Array.isArray(detail)) {
      messages = detail.map(
        (d) => `${d.loc?.slice(1).join(".") ?? "body"}: ${d.msg}`
      );
    } else if (typeof detail === "string") {
      messages = [detail];
    } else {
      // pydantic 标准错误也兼容
      if (Array.isArray(body?.detail)) {
        // noinspection JSUnresolvedReference
        messages = body.detail.map((d) => `${d.loc?.join(".")}: ${d.msg}`);
      } else {
        messages = [`HTTP ${resp.statusCode ?? resp.status}`];
      }
    }
    const err = new Error(messages.join("\n"));
    err.messages = messages;
    err.status = resp.status;
    throw err;
  }
  return body;
}

export async function apiSolve(payload) {
  const resp = await fetch(`${API_BASE}/api/solve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseResponse(resp);
}

export async function apiExamples() {
  const resp = await fetch(`${API_BASE}/api/examples`);
  return parseResponse(resp);
}

export async function apiHealth() {
  const resp = await fetch(`${API_BASE}/health`);
  return parseResponse(resp);
}

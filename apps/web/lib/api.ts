import { auth } from "./auth";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function refreshToken(): Promise<boolean> {
  const refresh = auth.getRefresh();
  if (!refresh) return false;
  const resp = await fetch(`${BASE}/api/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refresh }),
  });
  if (!resp.ok) {
    auth.clear();
    return false;
  }
  const data = await resp.json();
  auth.setSession(data.access_token, data.refresh_token, data.usuario);
  return true;
}

export async function api<T = any>(
  path: string,
  init: RequestInit = {},
  retried = false
): Promise<T> {
  const access = auth.getAccess();
  const resp = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(access ? { Authorization: `Bearer ${access}` } : {}),
      ...(init.headers || {}),
    },
  });

  if (resp.status === 401 && !retried && (await refreshToken())) {
    return api<T>(path, init, true);
  }

  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`${resp.status} ${text}`);
  }

  return resp.json() as Promise<T>;
}

export async function* chatStream(
  pergunta: string,
  sessaoId?: string
): AsyncGenerator<{ event: string; data: any }> {
  const access = auth.getAccess();
  const resp = await fetch(`${BASE}/api/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(access ? { Authorization: `Bearer ${access}` } : {}),
    },
    body: JSON.stringify({ pergunta, sessao_id: sessaoId }),
  });

  if (!resp.ok || !resp.body) {
    throw new Error(`stream failed: ${resp.status}`);
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    // Normaliza CRLF -> LF: o sse-starlette separa eventos com "\r\n\r\n",
    // e procurar "\n\n" cru nunca casaria (os \n não ficam adjacentes).
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");

    let idx;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const raw = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      const lines = raw.split("\n");
      let event = "message";
      let data = "";
      for (const line of lines) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (data) {
        try {
          yield { event, data: JSON.parse(data) };
        } catch {
          yield { event, data: data };
        }
      }
    }
  }
}

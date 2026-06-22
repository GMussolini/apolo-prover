import { auth } from "./auth";
import { parseSSE } from "./sse";

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

  yield* parseSSE(resp.body);
}

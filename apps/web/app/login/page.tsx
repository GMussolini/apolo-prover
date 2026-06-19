"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { auth } from "@/lib/auth";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function entrar(e: React.FormEvent) {
    e.preventDefault();
    setErro(null);
    setLoading(true);
    try {
      const resp = await fetch(`${BASE}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, senha }),
      });
      if (!resp.ok) throw new Error("credenciais inválidas");
      const data = await resp.json();
      auth.setSession(data.access_token, data.refresh_token, data.usuario);
      router.push("/chat");
    } catch (err: any) {
      setErro(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <h1 className="font-black text-5xl text-ap-text">APOLO</h1>
          <p className="text-ap-text-muted text-sm mt-2 font-mono">Prover Tecnologia</p>
        </div>

        <form onSubmit={entrar} className="space-y-4 bg-ap-surface border border-white/5 rounded-2xl p-8">
          <div>
            <label className="text-xs font-mono text-ap-text-muted uppercase tracking-wider mb-2 block">Email</label>
            <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
          </div>
          <div>
            <label className="text-xs font-mono text-ap-text-muted uppercase tracking-wider mb-2 block">Senha</label>
            <Input type="password" value={senha} onChange={(e) => setSenha(e.target.value)} required />
          </div>

          {erro && <p className="text-ap-danger text-xs">{erro}</p>}

          <Button type="submit" disabled={loading} className="w-full">
            {loading ? "entrando..." : "entrar"}
          </Button>
        </form>
      </div>
    </main>
  );
}

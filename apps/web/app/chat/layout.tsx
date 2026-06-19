"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { auth, type Usuario } from "@/lib/auth";
import { SessaoProvider, useSessao } from "@/lib/sessao-context";
import { SessoesSidebar } from "@/components/SessoesSidebar";

function ChatShell({
  usuario,
  children,
}: {
  usuario: Usuario;
  children: React.ReactNode;
}) {
  const router = useRouter();
  const { sessaoId, setSessaoId } = useSessao();

  return (
    <div className="flex h-screen bg-ap-black">
      <aside className="w-72 border-r border-white/5 bg-ap-surface flex flex-col">
        <div className="p-4 border-b border-white/5 flex items-center justify-between">
          <span className="font-mono text-sm text-ap-blue font-bold">APOLO</span>
          <button
            onClick={() => {
              auth.clear();
              router.push("/login");
            }}
            className="text-xs text-ap-text-faint hover:text-ap-text"
          >
            sair
          </button>
        </div>
        <SessoesSidebar sessaoAtiva={sessaoId} onSelecionar={setSessaoId} />
        <div className="p-3 border-t border-white/5 text-xs text-ap-text-muted">
          {usuario.nome} · <span className="font-mono">{usuario.email}</span>
        </div>
      </aside>
      <main className="flex-1 flex flex-col">{children}</main>
    </div>
  );
}

export default function ChatLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [usuario, setUsuario] = useState<Usuario | null>(null);

  useEffect(() => {
    const u = auth.getUsuario();
    if (!u) {
      router.push("/login");
      return;
    }
    setUsuario(u);
  }, [router]);

  if (!usuario) return null;

  return (
    <SessaoProvider>
      <ChatShell usuario={usuario}>{children}</ChatShell>
    </SessaoProvider>
  );
}

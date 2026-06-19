"use client";

import { createContext, useContext, useState } from "react";

type SessaoContextValue = {
  sessaoId: string | null;
  setSessaoId: (id: string | null) => void;
};

const Ctx = createContext<SessaoContextValue | null>(null);

export function SessaoProvider({ children }: { children: React.ReactNode }) {
  const [sessaoId, setSessaoId] = useState<string | null>(null);
  return (
    <Ctx.Provider value={{ sessaoId, setSessaoId }}>{children}</Ctx.Provider>
  );
}

export function useSessao() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useSessao fora do provider");
  return ctx;
}

import Link from "next/link";
import { SectionLabel } from "@/components/SectionLabel";
import { SkewHighlight } from "@/components/SkewHighlight";

export default function Home() {
  return (
    <>
      <nav className="fixed top-0 inset-x-0 z-50 backdrop-blur-xl bg-ap-black/80 border-b border-white/5">
        <div className="max-w-7xl mx-auto px-8 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-2 h-2 rounded-full bg-ap-blue animate-pulse" />
            <span className="font-mono text-xs font-bold text-white tracking-widest uppercase">
              MUSSTINS
            </span>
            <span className="text-ap-text-faint font-mono text-xs">·</span>
            <span className="font-mono text-xs text-ap-blue font-semibold">APOLO PROVER</span>
          </div>
          <Link href="/login" className="text-sm text-ap-text-muted hover:text-ap-text">
            entrar →
          </Link>
        </div>
      </nav>

      <section className="relative min-h-screen flex flex-col justify-center pt-14">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_60%_at_50%_0%,rgba(31,143,227,0.08),transparent)] pointer-events-none" />
        <div className="relative max-w-7xl mx-auto px-8 py-24 text-center">
          <SectionLabel>Musstins · Prover Tecnologia</SectionLabel>
          <h1 className="font-black text-[clamp(3rem,8vw,7rem)] leading-[0.92] tracking-tight mt-8 mb-8">
            <span className="text-white block">O assistente</span>
            <span className="block">
              <SkewHighlight>conversacional</SkewHighlight>
              <span className="text-white"> da</span>
            </span>
            <span className="text-white block mt-1">Prover</span>
          </h1>
          <p className="text-ap-text-muted text-lg md:text-xl max-w-2xl mx-auto leading-relaxed mb-12">
            Pergunte em linguagem natural sobre o <strong className="text-white">CRM</strong> e o{" "}
            <strong className="text-white">Controle de Recursos</strong> — texto ou voz, sem dashboard, sem SQL.
          </p>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-white/5 rounded-2xl overflow-hidden border border-white/5 max-w-3xl mx-auto">
            {[
              ["2", "Bases SQL Server"],
              ["6", "Domínios cravados"],
              ["~280", "Tabelas mapeadas"],
              ["∞", "Perguntas em PT-BR"],
            ].map(([n, label]) => (
              <div key={label} className="bg-ap-surface p-6 flex flex-col items-center gap-2">
                <span className="font-black text-4xl text-ap-blue tabular-nums">{n}</span>
                <span className="font-mono text-[10px] text-ap-text-faint uppercase tracking-widest text-center">
                  {label}
                </span>
              </div>
            ))}
          </div>

          <Link
            href="/login"
            className="inline-block mt-12 px-8 py-3 bg-ap-blue text-ap-black font-bold rounded-lg hover:bg-ap-blue-hover transition-colors"
          >
            entrar →
          </Link>
        </div>
      </section>

      <section className="py-32">
        <div className="max-w-7xl mx-auto px-8">
          <div className="mb-16">
            <SectionLabel>01 · Pipeline</SectionLabel>
            <h2 className="font-black text-4xl md:text-5xl text-white mt-4">Como uma pergunta vira resposta</h2>
          </div>
          <div className="grid md:grid-cols-6 gap-4">
            {[
              ["01", "Pergunta", "Texto ou voz, PT-BR natural"],
              ["02", "Contexto", "Carrega histórico da sessão e reformula follow-up"],
              ["03", "Classificação", "Identifica domínio + confidence"],
              ["04", "SQL", "Gera T-SQL com templates por ramo"],
              ["05", "Execução", "Pool read-only, sqlglot guard, 30s timeout"],
              ["06", "Resposta", "Markdown + Vega-Lite + voz"],
            ].map(([n, t, d]) => (
              <div key={n} className="bg-ap-surface border border-white/5 rounded-xl p-4">
                <p className="font-mono text-xs text-ap-blue mb-2">{n}</p>
                <p className="font-bold text-white mb-2">{t}</p>
                <p className="text-xs text-ap-text-muted">{d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <footer className="border-t border-white/5 py-8">
        <div className="max-w-7xl mx-auto px-8 flex justify-between items-center text-xs font-mono text-ap-text-faint">
          <span>MUSSTINS · APOLO PROVER · 2026</span>
          <span>Em desenvolvimento</span>
        </div>
      </footer>
    </>
  );
}

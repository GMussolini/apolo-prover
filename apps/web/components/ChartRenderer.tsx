"use client";

import { useEffect, useRef } from "react";
import vegaEmbed from "vega-embed";

// ─── Tema APOLO pra Vega-Lite (azul, escuro, limpo) ───
const BLUE = "#1F8FE3";
const MUTED = "#9CA3B0";
const GRID = "rgba(255,255,255,0.06)";
const LINE = "rgba(255,255,255,0.12)";

const APOLO_CONFIG: Record<string, any> = {
  font: "Inter, system-ui, sans-serif",
  background: "transparent",
  view: { stroke: "transparent" },
  bar: { cornerRadiusEnd: 5, color: BLUE },
  line: { color: BLUE, strokeWidth: 2.5, point: { color: BLUE, filled: true, size: 55 } },
  point: { color: BLUE, filled: true, size: 55 },
  arc: { innerRadius: 55, stroke: "#0A0F1A", strokeWidth: 2 },
  axis: {
    labelColor: MUTED,
    titleColor: MUTED,
    labelFontSize: 11,
    titleFontSize: 12,
    titleFontWeight: 600,
    titlePadding: 8,
    labelPadding: 6,
    gridColor: GRID,
    gridDash: [2, 4],
    domainColor: LINE,
    tickColor: LINE,
  },
  axisX: { labelAngle: 0 },
  legend: {
    labelColor: MUTED,
    titleColor: MUTED,
    labelFontSize: 11,
    titleFontSize: 11,
    symbolType: "circle",
    symbolSize: 80,
  },
  title: { color: "#F5F7FA", fontSize: 14, fontWeight: 700, anchor: "start", offset: 12 },
  range: {
    category: ["#1F8FE3", "#4FB0EF", "#5AC8D4", "#3ECF8E", "#FFB020", "#FF4D5E", "#0E6BB8", "#A78BFA"],
    ramp: ["#103253", "#1F8FE3", "#7CC4F5"],
    heatmap: ["#103253", "#1F8FE3", "#7CC4F5"],
  },
};

function isObj(v: any): boolean {
  return v && typeof v === "object" && !Array.isArray(v);
}
function mergeDeep(base: any, over: any): any {
  const out: Record<string, any> = { ...base };
  for (const k in over) {
    out[k] = isObj(out[k]) && isObj(over[k]) ? mergeDeep(out[k], over[k]) : over[k];
  }
  return out;
}

/** Aplica o tema APOLO e remove "sujeira" comum das specs do LLM. */
function temaApolo(spec: any, largura: number): any {
  const s = JSON.parse(JSON.stringify(spec || {}));
  s.background = "transparent";
  s.width = Math.max(220, largura);
  if (s.height == null) s.height = 260;
  s.autosize = { type: "fit", contains: "padding" };

  // remove legenda de cor por valor (gradiente redundante em série única)
  if (s.encoding?.color && s.encoding.color.type === "quantitative") {
    delete s.encoding.color;
  }
  s.config = mergeDeep(APOLO_CONFIG, s.config || {});
  return s;
}

export function ChartRenderer({ tipo, spec }: { tipo: string; spec: any }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || !spec || tipo === "tabela" || tipo === "kpi") return;
    const largura = el.clientWidth || 460;
    (vegaEmbed as any)(el, temaApolo(spec, largura), {
      actions: false,
      tooltip: true,
    }).catch(console.error);
  }, [spec, tipo]);

  if (tipo === "tabela") return null;

  if (tipo === "kpi") {
    const valor = spec?.data?.values?.[0]?.valor ?? spec?.data?.values?.[0]?.total ?? "—";
    const rotulo = spec?.title ?? spec?.data?.values?.[0]?.rotulo ?? null;
    return (
      <div className="mt-1 inline-flex min-w-[160px] flex-col items-start rounded-xl border border-ap-blue/20 bg-gradient-to-br from-ap-blue/10 to-transparent px-6 py-5">
        {rotulo && (
          <span className="font-mono text-[10px] uppercase tracking-widest text-ap-text-faint">
            {rotulo}
          </span>
        )}
        <span className="text-4xl font-black text-ap-blue">{valor}</span>
      </div>
    );
  }

  return (
    <div className="w-full max-w-2xl rounded-xl border border-white/5 bg-ap-surface/40 p-4">
      <div ref={ref} className="w-full" />
    </div>
  );
}

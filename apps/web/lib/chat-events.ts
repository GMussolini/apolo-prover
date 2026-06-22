export type ApoloEvent =
  | { type: "status"; text: string }
  | { type: "classification"; dominio: string; confidence: number }
  | { type: "sql"; sql: string }
  | { type: "token"; delta: string }
  | { type: "chart"; tipo: string; spec: unknown }
  | { type: "done"; [key: string]: unknown }
  | { type: "error"; text: string };

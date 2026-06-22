import { describe, it, expect } from "vitest";
import { parseSSE } from "../lib/sse";

function streamFrom(chunks: string[]): ReadableStream<Uint8Array> {
  const enc = new TextEncoder();
  return new ReadableStream({
    start(c) { for (const ch of chunks) c.enqueue(enc.encode(ch)); c.close(); },
  });
}

describe("parseSSE", () => {
  it("separa eventos com CRLF e parseia JSON", async () => {
    const s = streamFrom([
      'event: message\r\ndata: {"type":"status","text":"oi"}\r\n\r\n',
      'event: message\r\ndata: {"type":"token","delta":"a"}\r\n\r\n',
    ]);
    const got: any[] = [];
    for await (const ev of parseSSE(s)) got.push(ev.data);
    expect(got).toEqual([{ type: "status", text: "oi" }, { type: "token", delta: "a" }]);
  });
});

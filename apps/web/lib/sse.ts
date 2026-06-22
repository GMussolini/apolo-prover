export async function* parseSSE(
  stream: ReadableStream<Uint8Array>
): AsyncGenerator<{ event: string; data: any }> {
  const reader = stream.getReader();
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

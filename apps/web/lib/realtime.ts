import { auth } from "./auth";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type RealtimeEvento =
  | { type: "transcript_user"; texto: string }
  | { type: "transcript_apolo"; texto: string }
  | { type: "tool_call"; call_id: string; pergunta: string }
  | { type: "tool_done"; call_id: string; output: string }
  | { type: "estado"; estado: "idle" | "conectando" | "ouvindo" | "processando" | "falando" | "erro" }
  | { type: "nivel"; nivel: number }
  | { type: "erro"; mensagem: string };

export class RealtimeClient {
  private pc: RTCPeerConnection | null = null;
  private dc: RTCDataChannel | null = null;
  private audioEl: HTMLAudioElement | null = null;
  private localStream: MediaStream | null = null;
  private sessaoApoloId: string | null = null;
  private inicioMs = 0;
  private audioCtx: AudioContext | null = null;
  private rafId = 0;

  constructor(private onEvento: (evt: RealtimeEvento) => void) {}

  async iniciar(audioEl: HTMLAudioElement) {
    this.audioEl = audioEl;
    this.inicioMs = Date.now();
    this.onEvento({ type: "estado", estado: "conectando" });

    const sessResp = await fetch(`${BASE}/api/voice/session`, {
      method: "POST",
      headers: { Authorization: `Bearer ${auth.getAccess()}` },
    });
    if (!sessResp.ok) throw new Error("não autorizado");
    const sess = await sessResp.json();
    this.sessaoApoloId = sess.sessao_apolo_id;

    this.pc = new RTCPeerConnection();

    this.pc.ontrack = (ev) => {
      if (this.audioEl) this.audioEl.srcObject = ev.streams[0];
    };

    this.localStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    this.localStream.getTracks().forEach((t) => this.pc!.addTrack(t, this.localStream!));
    this.iniciarMedidorNivel(this.localStream);

    this.dc = this.pc.createDataChannel("oai-events");
    this.dc.onmessage = (e) => this.handleEvent(JSON.parse(e.data));

    const offer = await this.pc.createOffer();
    await this.pc.setLocalDescription(offer);

    const sdpResp = await fetch(`https://api.openai.com/v1/realtime/calls`, {
      method: "POST",
      body: offer.sdp,
      headers: {
        Authorization: `Bearer ${sess.ephemeral_token}`,
        "Content-Type": "application/sdp",
      },
    });
    const answer = { type: "answer", sdp: await sdpResp.text() } as RTCSessionDescriptionInit;
    await this.pc.setRemoteDescription(answer);

    this.onEvento({ type: "estado", estado: "ouvindo" });
  }

  private iniciarMedidorNivel(stream: MediaStream) {
    try {
      const ctx = new AudioContext();
      const src = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      src.connect(analyser);
      this.audioCtx = ctx;
      const buf = new Uint8Array(analyser.frequencyBinCount);
      const tick = () => {
        analyser.getByteTimeDomainData(buf);
        let sum = 0;
        for (let i = 0; i < buf.length; i++) {
          const x = (buf[i] - 128) / 128;
          sum += x * x;
        }
        const rms = Math.sqrt(sum / buf.length);
        this.onEvento({ type: "nivel", nivel: Math.min(1, rms * 3.2) });
        this.rafId = requestAnimationFrame(tick);
      };
      tick();
    } catch {
      /* sem medidor de nível — segue normal */
    }
  }

  /** Liga/desliga o microfone local (mute). Não afeta o áudio do APOLO. */
  mutar(mute: boolean) {
    this.localStream?.getAudioTracks().forEach((t) => (t.enabled = !mute));
    if (mute) this.onEvento({ type: "nivel", nivel: 0 });
  }

  private async handleEvent(evt: any) {
    if (evt.type === "conversation.item.input_audio_transcription.completed") {
      this.onEvento({ type: "transcript_user", texto: evt.transcript });
    }
    if (evt.type === "response.audio_transcript.done") {
      this.onEvento({ type: "transcript_apolo", texto: evt.transcript });
    }
    if (evt.type === "response.function_call_arguments.done") {
      const args = JSON.parse(evt.arguments);
      this.onEvento({ type: "tool_call", call_id: evt.call_id, pergunta: args.pergunta });
      this.onEvento({ type: "estado", estado: "processando" });

      const r = await fetch(`${BASE}/api/voice/tool-call`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${auth.getAccess()}`,
        },
        body: JSON.stringify({
          sessao_id: this.sessaoApoloId,
          call_id: evt.call_id,
          pergunta: args.pergunta,
        }),
      });
      const data = await r.json();
      this.onEvento({ type: "tool_done", call_id: evt.call_id, output: data.output });

      this.dc?.send(JSON.stringify({
        type: "conversation.item.create",
        item: {
          type: "function_call_output",
          call_id: evt.call_id,
          output: data.output,
        },
      }));
      this.dc?.send(JSON.stringify({ type: "response.create" }));
      this.onEvento({ type: "estado", estado: "falando" });
    }
    if (evt.type === "response.done") {
      this.onEvento({ type: "estado", estado: "ouvindo" });
    }
    if (evt.type === "error") {
      this.onEvento({ type: "erro", mensagem: evt.error?.message || "erro voz" });
      this.onEvento({ type: "estado", estado: "erro" });
    }
  }

  async parar() {
    if (this.rafId) cancelAnimationFrame(this.rafId);
    this.audioCtx?.close().catch(() => {});
    this.onEvento({ type: "nivel", nivel: 0 });
    if (this.localStream) this.localStream.getTracks().forEach((t) => t.stop());
    if (this.pc) this.pc.close();
    const minutos = (Date.now() - this.inicioMs) / 60000;
    if (minutos > 0.1) {
      fetch(`${BASE}/api/voice/consumo`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${auth.getAccess()}`,
        },
        body: JSON.stringify({ minutos }),
      }).catch(() => {});
    }
    this.onEvento({ type: "estado", estado: "idle" });
  }
}

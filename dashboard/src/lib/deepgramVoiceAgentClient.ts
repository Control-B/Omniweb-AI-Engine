/**
 * Minimal Deepgram Voice Agent browser client (WebSocket + linear16 PCM).
 * Auth pattern matches deepgram/browser-agent: ``new WebSocket(url, ["bearer", jwt])``.
 */

export type TranscriptLine = { role: "user" | "assistant"; content: string };

export type VoiceAgentHandlers = {
  onStructuredMessage?: (data: Record<string, unknown>) => void;
  onTranscript?: (line: TranscriptLine) => void;
  onError?: (message: string) => void;
  onClose?: () => void;
};

function getAudioContextClass(): typeof AudioContext | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    AudioContext?: typeof AudioContext;
    webkitAudioContext?: typeof AudioContext;
  };
  return w.AudioContext || w.webkitAudioContext || null;
}

function floatToInt16Buffer(channel: Float32Array): ArrayBuffer {
  const buf = new Int16Array(channel.length);
  for (let i = 0; i < channel.length; i += 1) {
    buf[i] = Math.min(1, Math.max(-1, channel[i] ?? 0)) * 0x7fff;
  }
  return buf.buffer;
}

export class DeepgramVoiceAgentSession {
  private ws: WebSocket | null = null;
  private micContext: AudioContext | null = null;
  private ttsContext: AudioContext | null = null;
  private micSource: MediaStreamAudioSourceNode | null = null;
  private processor: ScriptProcessorNode | null = null;
  private ttsAnalyser: AnalyserNode | null = null;
  private handlers: VoiceAgentHandlers;
  private settingsApplied = false;
  private pendingInjects: string[] = [];
  private scheduledSources = new Set<AudioBufferSourceNode>();
  private playHead = 0;
  private readonly outputSampleRate = 24000;

  constructor(handlers: VoiceAgentHandlers) {
    this.handlers = handlers;
  }

  async connect(params: {
    websocketUrl: string;
    accessToken: string;
    settings: Record<string, unknown>;
    enableMic: boolean;
  }): Promise<void> {
    await this.disconnect();
    this.settingsApplied = false;

    const scheme = "bearer";
    const socket = new WebSocket(params.websocketUrl, [scheme, params.accessToken]);
    socket.binaryType = "arraybuffer";

    await new Promise<void>((resolve, reject) => {
      const to = setTimeout(() => reject(new Error("WebSocket connection timeout")), 12_000);
      socket.addEventListener(
        "open",
        () => {
          clearTimeout(to);
          resolve();
        },
        { once: true },
      );
      socket.addEventListener(
        "error",
        () => {
          clearTimeout(to);
          reject(new Error("WebSocket connection failed"));
        },
        { once: true },
      );
    });

    this.ws = socket;
    socket.addEventListener("message", this.onMessage);
    socket.addEventListener("close", () => {
      this.handlers.onClose?.();
    });

    const settingsStr = JSON.stringify(params.settings);
    socket.send(settingsStr);

    const AudioContextClass = getAudioContextClass();
    if (!AudioContextClass) {
      throw new Error("Web Audio API is not available");
    }

    this.ttsContext = new AudioContextClass({
      latencyHint: "interactive",
      sampleRate: 48000,
    });
    this.ttsAnalyser = this.ttsContext.createAnalyser();
    this.ttsAnalyser.fftSize = 2048;
    this.ttsAnalyser.connect(this.ttsContext.destination);
    this.playHead = this.ttsContext.currentTime;

    if (params.enableMic) {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 16000,
        },
      });
      this.micContext = new AudioContextClass();
      await this.micContext.resume();
      this.micSource = this.micContext.createMediaStreamSource(stream);
      this.processor = this.micContext.createScriptProcessor(4096, 1, 1);
      this.micSource.connect(this.processor);
      this.processor.connect(this.micContext.destination);
      this.processor.onaudioprocess = (ev) => {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN || !this.settingsApplied) return;
        const pcm = floatToInt16Buffer(ev.inputBuffer.getChannelData(0));
        this.ws.send(pcm);
      };
    }

    await this.ttsContext.resume();
  }

  private onMessage = (ev: MessageEvent) => {
    if (ev.data instanceof ArrayBuffer) {
      this.playPcm(ev.data);
      return;
    }
    try {
      const data = JSON.parse(String(ev.data)) as Record<string, unknown>;
      this.handlers.onStructuredMessage?.(data);

      if (data.type === "SettingsApplied") {
        this.settingsApplied = true;
        this.flushInjects();
      }
      if (data.type === "UserStartedSpeaking") {
        this.stopPlayback();
      }
      if (data.type === "ConversationText" && (data.role === "user" || data.role === "assistant")) {
        this.handlers.onTranscript?.({
          role: data.role as "user" | "assistant",
          content: String(data.content ?? ""),
        });
      }
      if (data.type === "Error") {
        const msg =
          typeof data.message === "string"
            ? data.message
            : JSON.stringify(data.description ?? data);
        this.handlers.onError?.(msg);
      }
    } catch {
      /* ignore non-json */
    }
  };

  private playPcm(buf: ArrayBuffer) {
    if (!this.ttsContext || !this.ttsAnalyser) return;
    const samples = new Int16Array(buf);
    if (samples.length === 0) return;

    const buffer = this.ttsContext.createBuffer(1, samples.length, this.outputSampleRate);
    const ch = buffer.getChannelData(0);
    for (let i = 0; i < samples.length; i += 1) {
      ch[i] = samples[i]! / 32768;
    }
    const src = this.ttsContext.createBufferSource();
    src.buffer = buffer;
    src.connect(this.ttsAnalyser);
    const t = this.ttsContext.currentTime;
    if (this.playHead < t) this.playHead = t;
    src.addEventListener("ended", () => this.scheduledSources.delete(src));
    src.start(this.playHead);
    this.playHead += buffer.duration;
    this.scheduledSources.add(src);
  }

  private stopPlayback() {
    this.scheduledSources.forEach((s) => {
      try {
        s.stop();
      } catch {
        /* ignore */
      }
    });
    this.scheduledSources.clear();
    if (this.ttsContext) this.playHead = this.ttsContext.currentTime;
  }

  private flushInjects() {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    for (const t of this.pendingInjects) {
      this.ws.send(JSON.stringify({ type: "InjectUserMessage", content: t }));
    }
    this.pendingInjects = [];
  }

  injectUserMessage(text: string) {
    const t = text.trim();
    if (!t || !this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    if (!this.settingsApplied) {
      this.pendingInjects.push(t);
      return;
    }
    this.ws.send(JSON.stringify({ type: "InjectUserMessage", content: t }));
  }

  async disconnect(): Promise<void> {
    this.settingsApplied = false;
    this.pendingInjects = [];
    if (this.ws) {
      try {
        this.ws.removeEventListener("message", this.onMessage);
        this.ws.close(1000, "client disconnect");
      } catch {
        /* ignore */
      }
      this.ws = null;
    }
    this.stopPlayback();
    if (this.processor) {
      try {
        this.processor.disconnect();
      } catch {
        /* ignore */
      }
      this.processor = null;
    }
    if (this.micSource) {
      try {
        this.micSource.disconnect();
      } catch {
        /* ignore */
      }
      this.micSource.mediaStream.getTracks().forEach((tr) => tr.stop());
      this.micSource = null;
    }
    if (this.micContext) {
      try {
        await this.micContext.close();
      } catch {
        /* ignore */
      }
      this.micContext = null;
    }
    if (this.ttsContext) {
      try {
        await this.ttsContext.close();
      } catch {
        /* ignore */
      }
      this.ttsContext = null;
    }
    this.ttsAnalyser = null;
  }
}

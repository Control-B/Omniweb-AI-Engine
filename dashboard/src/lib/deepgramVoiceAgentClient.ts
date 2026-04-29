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

/** Deepgram Voice Agent ``audio.input`` is linear16 @ 16 kHz — browser mic is usually 44.1/48 kHz. */
function float32To16kHzPcm(input: Float32Array, inputSampleRate: number): ArrayBuffer {
  if (!input.length) return new ArrayBuffer(0);
  if (inputSampleRate === 16000) {
    return floatToInt16Buffer(input);
  }
  const ratio = inputSampleRate / 16000;
  const outLen = Math.max(1, Math.floor(input.length / ratio));
  const out = new Int16Array(outLen);
  for (let i = 0; i < outLen; i += 1) {
    const srcPos = i * ratio;
    const i0 = Math.floor(srcPos);
    const i1 = Math.min(i0 + 1, input.length - 1);
    const frac = srcPos - i0;
    const s = (input[i0] ?? 0) * (1 - frac) + (input[i1] ?? 0) * frac;
    out[i] = Math.min(1, Math.max(-1, s)) * 0x7fff;
  }
  return out.buffer;
}

export class DeepgramVoiceAgentSession {
  private ws: WebSocket | null = null;
  private micContext: AudioContext | null = null;
  private ttsContext: AudioContext | null = null;
  private micSource: MediaStreamAudioSourceNode | null = null;
  private micStream: MediaStream | null = null;
  private processor: ScriptProcessorNode | null = null;
  private ttsAnalyser: AnalyserNode | null = null;
  private handlers: VoiceAgentHandlers;
  /** Queued until server sends Welcome (Deepgram Voice Agent message flow). */
  private pendingSettingsJson: string | null = null;
  private settingsApplied = false;
  private pendingInjects: string[] = [];
  private scheduledSources = new Set<AudioBufferSourceNode>();
  private playHead = 0;
  private readonly outputSampleRate = 24000;
  private welcomeTimer: ReturnType<typeof setTimeout> | null = null;
  private micNoiseFloor = 0.006;
  private micSpeechFrames = 0;
  private micSilenceFrames = 0;
  private micIsSpeaking = false;

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
    this.pendingSettingsJson = null;
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
    this.pendingSettingsJson = JSON.stringify(params.settings);
    socket.addEventListener("message", this.onMessage);
    socket.addEventListener("close", () => {
      this.handlers.onClose?.();
    });

    this.welcomeTimer = setTimeout(() => {
      this.welcomeTimer = null;
      this.handlers.onError?.(
        "Voice service did not send Welcome. Check the Deepgram token, network, and that the Voice Agent WebSocket URL is correct.",
      );
    }, 12_000);

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
          autoGainControl: false,
          sampleRate: 16000,
          // Supported by Safari/Chrome on some devices; ignored elsewhere.
          voiceIsolation: true,
        },
      });
        this.micStream = stream;
      this.micContext = new AudioContextClass();
      await this.micContext.resume();
      this.micSource = this.micContext.createMediaStreamSource(stream);
      this.processor = this.micContext.createScriptProcessor(4096, 1, 1);
      this.micSource.connect(this.processor);
      this.processor.connect(this.micContext.destination);
      const inRate = this.micContext.sampleRate;
      this.processor.onaudioprocess = (ev) => {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN || !this.settingsApplied) return;
        // Avoid feeding the assistant's own speaker output back into the microphone.
        if (this.scheduledSources.size > 0) return;
        const ch = ev.inputBuffer.getChannelData(0);
        const rms = Math.sqrt(ch.reduce((sum, sample) => sum + sample * sample, 0) / ch.length);
        let peak = 0;
        for (let i = 0; i < ch.length; i += 1) {
          peak = Math.max(peak, Math.abs(ch[i] ?? 0));
        }

        const speechThreshold = Math.max(0.018, this.micNoiseFloor * 3.4);
        const releaseThreshold = Math.max(0.012, this.micNoiseFloor * 2.2);
        const hasSpeechEnergy = rms >= speechThreshold && peak >= speechThreshold * 1.7;

        if (!this.micIsSpeaking && !hasSpeechEnergy) {
          this.micNoiseFloor = this.micNoiseFloor * 0.96 + rms * 0.04;
          this.micSpeechFrames = 0;
          return;
        }

        if (hasSpeechEnergy) {
          this.micSpeechFrames += 1;
          this.micSilenceFrames = 0;
        } else {
          this.micSilenceFrames += 1;
        }

        if (!this.micIsSpeaking && this.micSpeechFrames < 3) return;
        this.micIsSpeaking = true;

        if (this.micIsSpeaking && rms < releaseThreshold && this.micSilenceFrames > 12) {
          this.micIsSpeaking = false;
          this.micSpeechFrames = 0;
          this.micSilenceFrames = 0;
          return;
        }

        const pcm = float32To16kHzPcm(ch, inRate);
        if (pcm.byteLength) this.ws.send(pcm);
      };
    }

    await this.ttsContext.resume();
  }

    setMicrophoneEnabled(enabled: boolean) {
      this.micStream?.getAudioTracks().forEach((track) => {
        track.enabled = enabled;
      });
    }

  private onMessage = (ev: MessageEvent) => {
    if (ev.data instanceof ArrayBuffer) {
      if (this.settingsApplied) {
        this.playPcm(ev.data);
      }
      return;
    }
    try {
      const data = JSON.parse(String(ev.data)) as Record<string, unknown>;
      this.handlers.onStructuredMessage?.(data);

      if (data.type === "Welcome" && this.ws && this.pendingSettingsJson) {
        if (this.welcomeTimer) {
          clearTimeout(this.welcomeTimer);
          this.welcomeTimer = null;
        }
        this.ws.send(this.pendingSettingsJson);
        this.pendingSettingsJson = null;
      }

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
    if (this.welcomeTimer) {
      clearTimeout(this.welcomeTimer);
      this.welcomeTimer = null;
    }
    this.pendingSettingsJson = null;
    this.settingsApplied = false;
    this.pendingInjects = [];
    this.micNoiseFloor = 0.006;
    this.micSpeechFrames = 0;
    this.micSilenceFrames = 0;
    this.micIsSpeaking = false;
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
      this.micSource = null;
    }
      if (this.micStream) {
        this.micStream.getTracks().forEach((track) => track.stop());
        this.micStream = null;
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

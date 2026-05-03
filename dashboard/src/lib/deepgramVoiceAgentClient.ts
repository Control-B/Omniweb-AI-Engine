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

type SpeechMediaTrackConstraints = MediaTrackConstraints & {
  voiceIsolation?: boolean;
  googEchoCancellation?: boolean;
  googNoiseSuppression?: boolean;
  googHighpassFilter?: boolean;
  googAutoGainControl?: boolean;
};

function getAudioContextClass(): typeof AudioContext | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    AudioContext?: typeof AudioContext;
    webkitAudioContext?: typeof AudioContext;
  };
  return w.AudioContext || w.webkitAudioContext || null;
}

function speechAudioConstraints(): MediaStreamConstraints {
  const audio: SpeechMediaTrackConstraints = {
    channelCount: { ideal: 1 },
    echoCancellation: { ideal: true },
    noiseSuppression: { ideal: true },
    autoGainControl: { ideal: true },
    sampleRate: { ideal: 16000 },
    sampleSize: { ideal: 16 },
    voiceIsolation: true,
    googEchoCancellation: true,
    googNoiseSuppression: true,
    googHighpassFilter: true,
    googAutoGainControl: true,
  };
  return { audio };
}

async function optimizeSpeechTrack(stream: MediaStream): Promise<void> {
  const [track] = stream.getAudioTracks();
  if (!track) return;
  track.contentHint = "speech";
  const constraints = speechAudioConstraints().audio;
  if (constraints && typeof constraints !== "boolean" && typeof track.applyConstraints === "function") {
    await track.applyConstraints(constraints).catch(() => {
      // Some browsers ignore unknown constraints at getUserMedia but reject them here.
    });
  }
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
  private micHighPass: BiquadFilterNode | null = null;
  private micCompressor: DynamicsCompressorNode | null = null;
  private micMutedOutput: GainNode | null = null;
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
  private keepAliveTimer: ReturnType<typeof setInterval> | null = null;
  private lastClientMessageAt = 0;

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
      const stream = await navigator.mediaDevices.getUserMedia(speechAudioConstraints());
      await optimizeSpeechTrack(stream);
      this.micStream = stream;
      this.micContext = new AudioContextClass();
      await this.micContext.resume();
      this.micSource = this.micContext.createMediaStreamSource(stream);
      this.micHighPass = this.micContext.createBiquadFilter();
      this.micHighPass.type = "highpass";
      this.micHighPass.frequency.value = 85;
      this.micHighPass.Q.value = 0.7;
      this.micCompressor = this.micContext.createDynamicsCompressor();
      this.micCompressor.threshold.value = -45;
      this.micCompressor.knee.value = 24;
      this.micCompressor.ratio.value = 4;
      this.micCompressor.attack.value = 0.003;
      this.micCompressor.release.value = 0.25;
      this.micMutedOutput = this.micContext.createGain();
      this.micMutedOutput.gain.value = 0;
      this.processor = this.micContext.createScriptProcessor(4096, 1, 1);
      this.micSource.connect(this.micHighPass);
      this.micHighPass.connect(this.micCompressor);
      this.micCompressor.connect(this.processor);
      this.processor.connect(this.micMutedOutput);
      this.micMutedOutput.connect(this.micContext.destination);
      const inRate = this.micContext.sampleRate;
      this.processor.onaudioprocess = (ev) => {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN || !this.settingsApplied) return;
        const ch = ev.inputBuffer.getChannelData(0);
        // Deepgram Voice Agent expects continuous binary mic audio after SettingsApplied.
        // Browser constraints and Web Audio cleanup handle noise/echo without starving ASR.
        const pcm = float32To16kHzPcm(ch, inRate);
        if (pcm.byteLength) this.sendBinary(pcm);
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
        this.sendText(this.pendingSettingsJson);
        this.pendingSettingsJson = null;
      }

      if (data.type === "SettingsApplied") {
        this.settingsApplied = true;
        this.startKeepAlive();
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
      this.sendJson({ type: "InjectUserMessage", content: t });
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
    this.sendJson({ type: "InjectUserMessage", content: t });
  }

  private sendBinary(payload: ArrayBuffer) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    this.ws.send(payload);
    this.lastClientMessageAt = Date.now();
  }

  private sendText(payload: string) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    this.ws.send(payload);
    this.lastClientMessageAt = Date.now();
  }

  private sendJson(payload: Record<string, unknown>) {
    this.sendText(JSON.stringify(payload));
  }

  private startKeepAlive() {
    this.stopKeepAlive();
    this.lastClientMessageAt = Date.now();
    this.keepAliveTimer = setInterval(() => {
      if (!this.ws || this.ws.readyState !== WebSocket.OPEN || !this.settingsApplied) return;
      if (Date.now() - this.lastClientMessageAt >= 7_500) {
        this.sendJson({ type: "KeepAlive" });
      }
    }, 2_000);
  }

  private stopKeepAlive() {
    if (this.keepAliveTimer) {
      clearInterval(this.keepAliveTimer);
      this.keepAliveTimer = null;
    }
  }

  async disconnect(): Promise<void> {
    if (this.welcomeTimer) {
      clearTimeout(this.welcomeTimer);
      this.welcomeTimer = null;
    }
    this.pendingSettingsJson = null;
    this.settingsApplied = false;
    this.pendingInjects = [];
    this.lastClientMessageAt = 0;
    this.stopKeepAlive();
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
    if (this.micMutedOutput) {
      try {
        this.micMutedOutput.disconnect();
      } catch {
        /* ignore */
      }
      this.micMutedOutput = null;
    }
    if (this.micCompressor) {
      try {
        this.micCompressor.disconnect();
      } catch {
        /* ignore */
      }
      this.micCompressor = null;
    }
    if (this.micHighPass) {
      try {
        this.micHighPass.disconnect();
      } catch {
        /* ignore */
      }
      this.micHighPass = null;
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

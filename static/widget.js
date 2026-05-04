/* eslint-disable */
/**
 * Omniweb universal embeddable widget.
 *
 * Customer install snippet (also used by omniweb.ai itself):
 *
 *   <script src="https://<engine-host>/widget.js"
 *           data-tenant-id="PUBLIC_WIDGET_KEY" async></script>
 *
 * One file, one snippet, one widget. Renders a floating launcher + chat
 * panel inside a shadow root, and connects to Deepgram Voice Agent for
 * voice mode and our /api/widget/chat endpoint for text mode.
 */
(function () {
  "use strict";

  if (typeof window === "undefined" || typeof document === "undefined") return;
  if (window.__OMNIWEB_WIDGET_LOADED__) return;
  window.__OMNIWEB_WIDGET_LOADED__ = true;

  var SCRIPT = document.currentScript || (function () {
    var scripts = document.getElementsByTagName("script");
    return scripts[scripts.length - 1] || null;
  })();
  if (!SCRIPT) return;

  var publicWidgetId =
    SCRIPT.getAttribute("data-tenant-id") ||
    SCRIPT.getAttribute("data-widget-key") ||
    (SCRIPT.dataset && (SCRIPT.dataset.tenantId || SCRIPT.dataset.widgetKey)) ||
    "";
  if (!publicWidgetId) {
    console.warn("[Omniweb] Missing data-tenant-id or data-widget-key on widget script.");
    return;
  }

  var apiBase;
  try {
    apiBase = new URL(SCRIPT.src, window.location.href).origin;
  } catch (_) {
    console.warn("[Omniweb] Invalid widget script URL.");
    return;
  }

  var STORAGE_KEY = "omniweb_session_id";
  var SILENCE_FALLBACK_MS = 250;
  var SILENCE_FRAME_SAMPLES = 1600; // 100 ms of linear16 @ 16 kHz
  var KEEPALIVE_IDLE_MS = 7500;
  var WELCOME_TIMEOUT_MS = 12000;
  var NOISE_GATE_RMS = 0.012;
  var NOISE_GATE_PEAK = 0.04;
  var MIN_SPEECH_FRAMES = 2;
  var SPEECH_HANGOVER_MS = 650;
  var BARGE_IN_DELAY_MS = 300;
  var BARGE_IN_SPEECH_WINDOW_MS = 900;

  // ---------- helpers --------------------------------------------------------

  function uuid() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") {
      return window.crypto.randomUUID();
    }
    return "ow_" + Math.random().toString(36).slice(2) + Date.now().toString(36);
  }

  function getSessionId() {
    try {
      var v = window.localStorage.getItem(STORAGE_KEY);
      if (v) return v;
      var n = uuid();
      window.localStorage.setItem(STORAGE_KEY, n);
      return n;
    } catch (_) {
      return uuid();
    }
  }

  function request(path, payload) {
    return fetch(apiBase + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then(function (response) {
      return response
        .json()
        .catch(function () {
          return {};
        })
        .then(function (data) {
          if (!response.ok) {
            var msg =
              (data && data.detail) ||
              (data && data.error && data.error.message) ||
              ("Request failed (" + response.status + ")");
            throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
          }
          return data;
        });
    });
  }

  function getJson(path) {
    return fetch(apiBase + path, {
      method: "GET",
      headers: { Accept: "application/json" },
    }).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    });
  }

  function track(eventType, metadata) {
    return request("/api/widget/events", {
      publicWidgetId: publicWidgetId,
      sessionId: getSessionId(),
      eventType: eventType,
      domain: window.location.hostname,
      pageUrl: window.location.href,
      metadata: metadata || {},
    }).catch(function () {});
  }

  function installPing() {
    return request("/api/widget/install-ping", {
      publicWidgetId: publicWidgetId,
      domain: window.location.hostname,
      pageUrl: window.location.href,
    }).catch(function () {});
  }

  // ---------- audio plumbing -------------------------------------------------

  function getAudioContextClass() {
    return window.AudioContext || window.webkitAudioContext || null;
  }

  function speechAudioConstraints() {
    return {
      audio: {
        channelCount: { ideal: 1 },
        echoCancellation: { ideal: true },
        noiseSuppression: { ideal: true },
        autoGainControl: { ideal: true },
        sampleRate: { ideal: 16000 },
        sampleSize: { ideal: 16 },
        // Vendor-prefixed hints — browsers ignore unknown keys.
        voiceIsolation: true,
        googEchoCancellation: true,
        googNoiseSuppression: true,
        googHighpassFilter: true,
        googAutoGainControl: true,
      },
    };
  }

  function applySpeechHints(stream) {
    try {
      var tracks = stream.getAudioTracks();
      if (!tracks.length) return Promise.resolve();
      var track = tracks[0];
      try { track.contentHint = "speech"; } catch (_) {}
      if (typeof track.applyConstraints === "function") {
        return track
          .applyConstraints(speechAudioConstraints().audio)
          .catch(function () {});
      }
    } catch (_) {}
    return Promise.resolve();
  }

  function floatToInt16(channel) {
    var out = new Int16Array(channel.length);
    for (var i = 0; i < channel.length; i += 1) {
      var s = channel[i];
      if (s > 1) s = 1;
      else if (s < -1) s = -1;
      out[i] = s * 0x7fff;
    }
    return out.buffer;
  }

  function float32To16kHzPcm(input, inputSampleRate) {
    if (!input.length) return new ArrayBuffer(0);
    if (inputSampleRate === 16000) return floatToInt16(input);
    var ratio = inputSampleRate / 16000;
    var outLen = Math.max(1, Math.floor(input.length / ratio));
    var out = new Int16Array(outLen);
    for (var i = 0; i < outLen; i += 1) {
      var srcPos = i * ratio;
      var i0 = Math.floor(srcPos);
      var i1 = Math.min(i0 + 1, input.length - 1);
      var frac = srcPos - i0;
      var s = (input[i0] || 0) * (1 - frac) + (input[i1] || 0) * frac;
      if (s > 1) s = 1;
      else if (s < -1) s = -1;
      out[i] = s * 0x7fff;
    }
    return out.buffer;
  }

  function looksLikeSpeech(channel) {
    if (!channel || !channel.length) return false;
    var sum = 0;
    var peak = 0;
    for (var i = 0; i < channel.length; i += 1) {
      var v = channel[i] || 0;
      var a = v < 0 ? -v : v;
      sum += v * v;
      if (a > peak) peak = a;
    }
    var rms = Math.sqrt(sum / channel.length);
    return rms >= NOISE_GATE_RMS && peak >= NOISE_GATE_PEAK;
  }

  // ---------- Deepgram voice agent session (vanilla port) --------------------

  function VoiceSession(handlers) {
    this.handlers = handlers || {};
    this.ws = null;
    this.micContext = null;
    this.ttsContext = null;
    this.micStream = null;
    this.micSource = null;
    this.micHighPass = null;
    this.micCompressor = null;
    this.micMutedOutput = null;
    this.processor = null;
    this.ttsAnalyser = null;
    this.pendingSettingsJson = null;
    this.settingsApplied = false;
    this.scheduledSources = [];
    this.playHead = 0;
    this.outputSampleRate = 24000;
    this.welcomeTimer = null;
    this.keepAliveTimer = null;
    this.audioWatchdog = null;
    this.lastClientMessageAt = 0;
    this.lastBinaryAudioAt = 0;
    this.lastSpeechAudioAt = 0;
    this.lastSpeechFrameAt = 0;
    this.speechFrameCount = 0;
    this.bargeInTimer = null;
  }

  VoiceSession.prototype.connect = function (params) {
    var self = this;
    return self.disconnect().then(function () {
      self.pendingSettingsJson = null;
      self.settingsApplied = false;
      var socket = new WebSocket(params.websocketUrl, ["bearer", params.accessToken]);
      socket.binaryType = "arraybuffer";

      return new Promise(function (resolve, reject) {
        var to = setTimeout(function () {
          reject(new Error("WebSocket connection timeout"));
        }, 12000);
        socket.addEventListener(
          "open",
          function () {
            clearTimeout(to);
            resolve();
          },
          { once: true }
        );
        socket.addEventListener(
          "error",
          function () {
            clearTimeout(to);
            reject(new Error("WebSocket connection failed"));
          },
          { once: true }
        );
      }).then(function () {
        self.ws = socket;
        self.pendingSettingsJson = JSON.stringify(params.settings || {});
        socket.addEventListener("message", function (ev) {
          self._onMessage(ev);
        });
        socket.addEventListener("close", function () {
          if (self.handlers.onClose) self.handlers.onClose();
        });

        self.welcomeTimer = setTimeout(function () {
          self.welcomeTimer = null;
          if (self.handlers.onError) {
            self.handlers.onError(
              "Voice service did not send Welcome. Check the engine token, network, and Voice Agent URL."
            );
          }
        }, WELCOME_TIMEOUT_MS);

        var AudioContextClass = getAudioContextClass();
        if (!AudioContextClass) throw new Error("Web Audio API is not available");

        self.ttsContext = new AudioContextClass({ latencyHint: "interactive", sampleRate: 48000 });
        self.ttsAnalyser = self.ttsContext.createAnalyser();
        self.ttsAnalyser.fftSize = 2048;
        self.ttsAnalyser.connect(self.ttsContext.destination);
        self.playHead = self.ttsContext.currentTime;

        if (!params.enableMic) return self.ttsContext.resume();

        return navigator.mediaDevices
          .getUserMedia(speechAudioConstraints())
          .then(function (stream) {
            return applySpeechHints(stream).then(function () {
              self.micStream = stream;
              self.micContext = new AudioContextClass();
              return self.micContext.resume().then(function () {
                self.micSource = self.micContext.createMediaStreamSource(stream);
                self.micHighPass = self.micContext.createBiquadFilter();
                self.micHighPass.type = "highpass";
                self.micHighPass.frequency.value = 85;
                self.micHighPass.Q.value = 0.7;
                self.micCompressor = self.micContext.createDynamicsCompressor();
                self.micCompressor.threshold.value = -45;
                self.micCompressor.knee.value = 24;
                self.micCompressor.ratio.value = 4;
                self.micCompressor.attack.value = 0.003;
                self.micCompressor.release.value = 0.25;
                self.micMutedOutput = self.micContext.createGain();
                self.micMutedOutput.gain.value = 0;
                self.processor = self.micContext.createScriptProcessor(4096, 1, 1);
                self.micSource.connect(self.micHighPass);
                self.micHighPass.connect(self.micCompressor);
                self.micCompressor.connect(self.processor);
                self.processor.connect(self.micMutedOutput);
                self.micMutedOutput.connect(self.micContext.destination);
                var inRate = self.micContext.sampleRate;
                self.processor.onaudioprocess = function (ev) {
                  if (!self.ws || self.ws.readyState !== WebSocket.OPEN || !self.settingsApplied) return;
                  self._ensureMicRunning();
                  var ch = ev.inputBuffer.getChannelData(0);
                  var now = Date.now();
                  var speechLike = looksLikeSpeech(ch);
                  if (speechLike) {
                    self.speechFrameCount += 1;
                    self.lastSpeechFrameAt = now;
                  } else if (now - self.lastSpeechFrameAt > SPEECH_HANGOVER_MS) {
                    self.speechFrameCount = 0;
                  }
                  if (self.speechFrameCount >= MIN_SPEECH_FRAMES || (self.lastSpeechAudioAt && now - self.lastSpeechFrameAt <= SPEECH_HANGOVER_MS)) {
                    var pcm = float32To16kHzPcm(ch, inRate);
                    if (pcm.byteLength) {
                      if (speechLike) self.lastSpeechAudioAt = now;
                      self._sendBinary(pcm);
                    }
                  } else {
                    self._sendSilence();
                  }
                };
                return self.ttsContext.resume();
              });
            });
          });
      });
    });
  };

  VoiceSession.prototype._ensureMicRunning = function () {
    var ctx = this.micContext;
    if (!ctx || ctx.state === "running") return;
    try { ctx.resume(); } catch (_) {}
  };

  VoiceSession.prototype._sendSilence = function () {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    this._sendBinary(new Int16Array(SILENCE_FRAME_SAMPLES).buffer);
  };

  VoiceSession.prototype._sendBinary = function (payload) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    this.ws.send(payload);
    var now = Date.now();
    this.lastClientMessageAt = now;
    this.lastBinaryAudioAt = now;
  };

  VoiceSession.prototype._sendText = function (payload) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    this.ws.send(payload);
    this.lastClientMessageAt = Date.now();
  };

  VoiceSession.prototype._sendJson = function (payload) {
    this._sendText(JSON.stringify(payload));
  };

  VoiceSession.prototype._startKeepAlive = function () {
    var self = this;
    self._stopKeepAlive();
    self.lastClientMessageAt = Date.now();
    self.keepAliveTimer = setInterval(function () {
      if (!self.ws || self.ws.readyState !== WebSocket.OPEN || !self.settingsApplied) return;
      if (Date.now() - self.lastClientMessageAt >= KEEPALIVE_IDLE_MS) {
        self._sendJson({ type: "KeepAlive" });
      }
    }, 2000);
  };

  VoiceSession.prototype._stopKeepAlive = function () {
    if (this.keepAliveTimer) {
      clearInterval(this.keepAliveTimer);
      this.keepAliveTimer = null;
    }
  };

  VoiceSession.prototype._startWatchdog = function () {
    var self = this;
    self._stopWatchdog();
    self.lastBinaryAudioAt = Date.now();
    self.audioWatchdog = setInterval(function () {
      if (!self.ws || self.ws.readyState !== WebSocket.OPEN || !self.settingsApplied) return;
      self._ensureMicRunning();
      if (Date.now() - self.lastBinaryAudioAt >= SILENCE_FALLBACK_MS) {
        self._sendSilence();
      }
    }, 100);
  };

  VoiceSession.prototype._stopWatchdog = function () {
    if (this.audioWatchdog) {
      clearInterval(this.audioWatchdog);
      this.audioWatchdog = null;
    }
  };

  VoiceSession.prototype._stopPlayback = function () {
    if (this.bargeInTimer) {
      clearTimeout(this.bargeInTimer);
      this.bargeInTimer = null;
    }
    for (var i = 0; i < this.scheduledSources.length; i += 1) {
      try { this.scheduledSources[i].stop(); } catch (_) {}
    }
    this.scheduledSources = [];
    if (this.ttsContext) this.playHead = this.ttsContext.currentTime;
  };

  VoiceSession.prototype._maybeStopPlaybackForBargeIn = function () {
    var self = this;
    if (Date.now() - self.lastSpeechAudioAt > BARGE_IN_SPEECH_WINDOW_MS) return;
    if (self.bargeInTimer) clearTimeout(self.bargeInTimer);
    self.bargeInTimer = setTimeout(function () {
      self.bargeInTimer = null;
      if (Date.now() - self.lastSpeechAudioAt <= BARGE_IN_SPEECH_WINDOW_MS) {
        self._stopPlayback();
      }
    }, BARGE_IN_DELAY_MS);
  };

  VoiceSession.prototype._playPcm = function (buf) {
    if (!this.ttsContext || !this.ttsAnalyser) return;
    var samples = new Int16Array(buf);
    if (!samples.length) return;
    var buffer = this.ttsContext.createBuffer(1, samples.length, this.outputSampleRate);
    var ch = buffer.getChannelData(0);
    for (var i = 0; i < samples.length; i += 1) ch[i] = samples[i] / 32768;
    var src = this.ttsContext.createBufferSource();
    src.buffer = buffer;
    src.connect(this.ttsAnalyser);
    var t = this.ttsContext.currentTime;
    if (this.playHead < t) this.playHead = t;
    var self = this;
    src.addEventListener("ended", function () {
      var idx = self.scheduledSources.indexOf(src);
      if (idx >= 0) self.scheduledSources.splice(idx, 1);
    });
    src.start(this.playHead);
    this.playHead += buffer.duration;
    this.scheduledSources.push(src);
  };

  VoiceSession.prototype._onMessage = function (ev) {
    if (ev.data instanceof ArrayBuffer) {
      if (this.settingsApplied) this._playPcm(ev.data);
      return;
    }
    var data;
    try { data = JSON.parse(String(ev.data)); } catch (_) { return; }
    if (this.handlers.onStructuredMessage) this.handlers.onStructuredMessage(data);

    if (data.type === "Welcome" && this.ws && this.pendingSettingsJson) {
      if (this.welcomeTimer) {
        clearTimeout(this.welcomeTimer);
        this.welcomeTimer = null;
      }
      this._sendText(this.pendingSettingsJson);
      this.pendingSettingsJson = null;
    }
    if (data.type === "SettingsApplied") {
      this.settingsApplied = true;
      this._sendSilence();
      this._startKeepAlive();
      this._startWatchdog();
    }
    if (data.type === "UserStartedSpeaking") this._maybeStopPlaybackForBargeIn();
    if (data.type === "AgentStartedSpeaking" && this.handlers.onAgentSpeaking) {
      if (this.bargeInTimer) {
        clearTimeout(this.bargeInTimer);
        this.bargeInTimer = null;
      }
      this.handlers.onAgentSpeaking(true);
    }
    if ((data.type === "AgentAudioDone" || data.type === "AgentStoppedSpeaking") && this.handlers.onAgentSpeaking) {
      this.handlers.onAgentSpeaking(false);
    }
    if (data.type === "ConversationText" && (data.role === "user" || data.role === "assistant")) {
      if (this.handlers.onTranscript) {
        this.handlers.onTranscript({ role: data.role, content: String(data.content || "") });
      }
    }
    if (data.type === "Error" && this.handlers.onError) {
      var msg = typeof data.message === "string" ? data.message : JSON.stringify(data.description || data);
      this.handlers.onError(msg);
    }
  };

  VoiceSession.prototype.injectUserMessage = function (text) {
    var t = (text || "").trim();
    if (!t || !this.ws || this.ws.readyState !== WebSocket.OPEN || !this.settingsApplied) return;
    this._sendJson({ type: "InjectUserMessage", content: t });
  };

  VoiceSession.prototype.setMicEnabled = function (enabled) {
    if (!this.micStream) return;
    var tracks = this.micStream.getAudioTracks();
    for (var i = 0; i < tracks.length; i += 1) tracks[i].enabled = !!enabled;
  };

  VoiceSession.prototype.disconnect = function () {
    var self = this;
    if (self.welcomeTimer) {
      clearTimeout(self.welcomeTimer);
      self.welcomeTimer = null;
    }
    self.pendingSettingsJson = null;
    self.settingsApplied = false;
    self.lastClientMessageAt = 0;
    self.lastBinaryAudioAt = 0;
    self.lastSpeechAudioAt = 0;
    self.lastSpeechFrameAt = 0;
    self.speechFrameCount = 0;
    if (self.bargeInTimer) {
      clearTimeout(self.bargeInTimer);
      self.bargeInTimer = null;
    }
    self._stopKeepAlive();
    self._stopWatchdog();
    if (self.ws) {
      try { self.ws.close(1000, "client disconnect"); } catch (_) {}
      self.ws = null;
    }
    self._stopPlayback();
    var nodes = ["processor", "micMutedOutput", "micCompressor", "micHighPass", "micSource"];
    for (var i = 0; i < nodes.length; i += 1) {
      var n = self[nodes[i]];
      if (n) {
        try { n.disconnect(); } catch (_) {}
        self[nodes[i]] = null;
      }
    }
    if (self.micStream) {
      try {
        self.micStream.getTracks().forEach(function (t) { t.stop(); });
      } catch (_) {}
      self.micStream = null;
    }
    var closes = [];
    if (self.micContext) {
      try { closes.push(self.micContext.close()); } catch (_) {}
      self.micContext = null;
    }
    if (self.ttsContext) {
      try { closes.push(self.ttsContext.close()); } catch (_) {}
      self.ttsContext = null;
    }
    self.ttsAnalyser = null;
    return Promise.all(closes.map(function (p) { return Promise.resolve(p).catch(function () {}); }))
      .then(function () { return undefined; });
  };

  // ---------- UI -------------------------------------------------------------

  var STYLES = [
    "@keyframes ow-pulse { 0%, 100% { box-shadow: 0 10px 30px rgba(139,92,246,.45), 0 0 0 0 rgba(168,85,247,.45); } 50% { box-shadow: 0 14px 36px rgba(139,92,246,.55), 0 0 0 14px rgba(168,85,247,0); } }",
    "@keyframes ow-fade-in { from { opacity: 0; transform: translateY(8px) scale(.98); } to { opacity: 1; transform: translateY(0) scale(1); } }",
    "@keyframes ow-msg-in { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }",
    "@keyframes ow-dot { 0%, 80%, 100% { transform: scale(.6); opacity: .4; } 40% { transform: scale(1); opacity: 1; } }",
    ":host, * { box-sizing: border-box; }",
    ":host { all: initial; font-family: 'Inter', system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; -webkit-text-size-adjust: 100%; text-size-adjust: 100%; }",
    ".ow-root { position: fixed; z-index: 2147483647; bottom: 24px; }",
    ".ow-root.right { right: 24px; }",
    ".ow-root.left { left: 24px; }",
    ".ow-launcher { width: 60px; height: 60px; border-radius: 9999px; border: 0; cursor: pointer; padding: 0; color: #fff; background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #a855f7 100%); box-shadow: 0 10px 30px rgba(139,92,246,.45), inset 0 1px 0 rgba(255,255,255,.2); transition: transform .18s ease, box-shadow .18s ease; display: flex; align-items: center; justify-content: center; animation: ow-pulse 3.5s ease-in-out infinite; }",
    ".ow-launcher:hover { transform: translateY(-2px) scale(1.04); }",
    ".ow-launcher:active { transform: scale(.96); }",
    ".ow-launcher svg { width: 26px; height: 26px; filter: drop-shadow(0 1px 2px rgba(0,0,0,.25)); }",
    ".ow-panel { display: none; position: fixed; z-index: 2147483646; right: 24px; bottom: 100px; width: 380px; max-width: calc(100vw - 24px); height: min(640px, calc(100dvh - 120px)); max-height: calc(100dvh - 120px); border-radius: 22px; overflow: hidden; background: linear-gradient(180deg, #110b1f 0%, #0a0712 100%); color: #ede9fe; border: 1px solid rgba(139,92,246,.18); box-shadow: 0 30px 80px rgba(15,5,40,.65), 0 0 0 1px rgba(255,255,255,.02); flex-direction: column; font-size: 14px; line-height: 1.45; }",
    ".ow-panel.open { display: flex; animation: ow-fade-in .22s ease-out; }",
    ".ow-root.left .ow-panel { left: 24px; right: auto; }",
    "@media (max-width: 480px) { .ow-panel { right: 12px; left: 12px; bottom: 96px; width: auto; max-width: none; height: calc(100dvh - 120px); max-height: calc(100dvh - 120px); } .ow-root.left .ow-panel { left: 12px; right: 12px; } }",
    ".ow-panel::before { content: ''; position: absolute; top: -1px; left: -1px; right: -1px; height: 120px; background: radial-gradient(120% 100% at 50% 0%, rgba(139,92,246,.22) 0%, rgba(139,92,246,0) 70%); pointer-events: none; }",
    ".ow-header { position: relative; display: flex; align-items: center; gap: 12px; padding: 18px 18px 14px; border-bottom: 1px solid rgba(139,92,246,.12); flex-shrink: 0; }",
    ".ow-avatar { width: 38px; height: 38px; border-radius: 9999px; flex-shrink: 0; background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #d946ef 100%); display: flex; align-items: center; justify-content: center; color: #fff; box-shadow: 0 4px 14px rgba(139,92,246,.45), inset 0 1px 0 rgba(255,255,255,.25); }",
    ".ow-avatar svg { width: 18px; height: 18px; }",
    ".ow-title { flex: 1; min-width: 0; }",
    ".ow-title-name { font-size: 15px; font-weight: 600; color: #fafaff; line-height: 1.2; margin: 0; letter-spacing: -0.01em; }",
    ".ow-title-sub { font-size: 12px; color: #a78bfa; margin-top: 3px; display: flex; align-items: center; gap: 6px; }",
    ".ow-status-dot { width: 6px; height: 6px; border-radius: 9999px; background: #22c55e; box-shadow: 0 0 0 3px rgba(34,197,94,.18); }",
    ".ow-close { background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.06); color: #c4b5fd; cursor: pointer; padding: 6px; border-radius: 10px; line-height: 0; transition: all .15s ease; }",
    ".ow-close:hover { background: rgba(139,92,246,.12); color: #fff; border-color: rgba(139,92,246,.3); }",
    ".ow-transcript { flex: 1; min-height: 0; overflow-y: auto; overscroll-behavior: contain; -webkit-overflow-scrolling: touch; padding: 14px 16px 4px; display: flex; flex-direction: column; gap: 10px; }",
    ".ow-transcript::-webkit-scrollbar { width: 6px; }",
    ".ow-transcript::-webkit-scrollbar-thumb { background: rgba(139,92,246,.2); border-radius: 9999px; }",
    ".ow-empty { color: #8b7eb8; font-size: 12px; line-height: 1.6; padding: 4px 2px; }",
    ".ow-error { background: linear-gradient(135deg, rgba(190,18,60,.25), rgba(127,29,29,.35)); border: 1px solid rgba(248,113,113,.3); color: #fecaca; font-size: 12px; line-height: 1.4; border-radius: 12px; padding: 10px 12px; }",
    ".ow-error button { margin-top: 4px; background: transparent; border: 0; color: #fca5a5; cursor: pointer; font-size: 12px; text-decoration: underline; padding: 0; }",
    ".ow-msg { border-radius: 14px; padding: 10px 13px; font-size: 14px; line-height: 1.45; word-wrap: break-word; overflow-wrap: anywhere; white-space: pre-wrap; animation: ow-msg-in .22s ease-out; }",
    ".ow-msg .ow-role { font-size: 10px; text-transform: uppercase; letter-spacing: .1em; opacity: .65; margin-bottom: 3px; font-weight: 600; }",
    ".ow-msg.user { background: linear-gradient(135deg, #7c3aed 0%, #8b5cf6 100%); margin-left: 32px; color: #fff; align-self: flex-end; max-width: 85%; box-shadow: 0 6px 18px rgba(124,58,237,.3); }",
    ".ow-msg.user .ow-role { color: rgba(255,255,255,.75); }",
    ".ow-msg.assistant { background: rgba(139,92,246,.08); border: 1px solid rgba(139,92,246,.18); color: #ede9fe; margin-right: 32px; align-self: flex-start; max-width: 90%; }",
    ".ow-msg.assistant .ow-role { color: #a78bfa; }",
    ".ow-booking-action { align-self: flex-start; max-width: 100%; margin: -2px 32px 4px 0; animation: ow-msg-in .22s ease-out; }",
    ".ow-booking-btn { display: inline-flex; width: auto; max-width: 100%; align-items: center; justify-content: center; gap: 8px; border: 0; border-radius: 12px; background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 60%, #a855f7 100%); color: #fff; padding: 11px 14px; font-size: 14px; font-weight: 700; cursor: pointer; text-decoration: none; box-shadow: 0 8px 22px rgba(139,92,246,.35); }",
    ".ow-booking-btn:hover { filter: brightness(1.08); }",
    "@media (max-width: 480px) { .ow-booking-action { align-self: stretch; margin-right: 0; } .ow-booking-btn { width: 100%; } }",
    ".ow-typing { display: inline-flex; gap: 4px; align-items: center; padding: 2px 0; }",
    ".ow-typing span { width: 6px; height: 6px; border-radius: 9999px; background: #a78bfa; animation: ow-dot 1.2s ease-in-out infinite; }",
    ".ow-typing span:nth-child(2) { animation-delay: .15s; }",
    ".ow-typing span:nth-child(3) { animation-delay: .3s; }",
    ".ow-lang { padding: 10px 16px 6px; flex-shrink: 0; }",
    ".ow-lang-label { font-size: 10px; text-transform: uppercase; letter-spacing: .14em; color: #8b7eb8; margin-bottom: 6px; font-weight: 600; }",
    ".ow-lang-btn { width: 100%; display: flex; align-items: center; justify-content: space-between; gap: 8px; background: rgba(255,255,255,.03); border: 1px solid rgba(139,92,246,.18); color: #ede9fe; padding: 10px 14px; border-radius: 12px; font-size: 14px; cursor: pointer; text-align: left; transition: all .15s ease; }",
    ".ow-lang-btn:hover:not(:disabled) { background: rgba(139,92,246,.1); border-color: rgba(139,92,246,.35); }",
    ".ow-lang-btn:disabled { opacity: .5; cursor: not-allowed; }",
    ".ow-lang-menu { position: relative; }",
    ".ow-lang-list { position: absolute; bottom: calc(100% + 4px); left: 0; right: 0; max-height: 200px; overflow-y: auto; background: #15102a; border: 1px solid rgba(139,92,246,.25); border-radius: 12px; padding: 4px 0; box-shadow: 0 18px 44px rgba(15,5,40,.7); list-style: none; margin: 0; z-index: 5; }",
    ".ow-lang-list li button { width: 100%; background: transparent; border: 0; color: #ede9fe; padding: 9px 14px; font-size: 14px; text-align: left; cursor: pointer; display: flex; align-items: center; gap: 10px; }",
    ".ow-lang-list li button:hover { background: rgba(139,92,246,.12); }",
    ".ow-modes { display: flex; gap: 8px; padding: 8px 16px; flex-shrink: 0; }",
    ".ow-mode { flex: 1; display: flex; align-items: center; justify-content: center; gap: 8px; padding: 12px; border-radius: 14px; border: 1px solid rgba(139,92,246,.18); background: rgba(255,255,255,.02); color: #c4b5fd; font-size: 14px; font-weight: 500; cursor: pointer; transition: all .18s ease; }",
    ".ow-mode:hover:not(:disabled):not(.active) { background: rgba(139,92,246,.08); border-color: rgba(139,92,246,.3); color: #ede9fe; }",
    ".ow-mode.active { background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 60%, #a855f7 100%); color: #fff; border-color: transparent; box-shadow: 0 8px 24px rgba(139,92,246,.4), inset 0 1px 0 rgba(255,255,255,.18); }",
    ".ow-mode:disabled { opacity: .5; cursor: not-allowed; }",
    ".ow-mode svg { width: 16px; height: 16px; }",
    ".ow-compose { display: flex; align-items: flex-end; gap: 8px; padding: 10px 14px 14px; flex-shrink: 0; }",
    ".ow-compose-wrap { flex: 1; min-width: 0; position: relative; display: flex; align-items: flex-end; background: rgba(255,255,255,.03); border: 1px solid rgba(139,92,246,.2); border-radius: 16px; padding: 4px 4px 4px 14px; transition: border-color .15s ease, box-shadow .15s ease; }",
    ".ow-compose-wrap:focus-within { border-color: rgba(139,92,246,.55); box-shadow: 0 0 0 4px rgba(139,92,246,.12); }",
    ".ow-input { flex: 1; min-width: 0; resize: none; background: transparent; border: 0; color: #fafaff; padding: 9px 6px 9px 0; font-family: inherit; font-size: 14px; line-height: 1.4; min-height: 38px; max-height: 110px; outline: none; }",
    ".ow-input::placeholder { color: #7c6ea3; }",
    ".ow-send { flex-shrink: 0; width: 38px; height: 38px; border-radius: 12px; border: 0; background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 60%, #a855f7 100%); color: #fff; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: all .18s ease; box-shadow: 0 4px 14px rgba(139,92,246,.45); }",
    ".ow-send:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 6px 20px rgba(139,92,246,.55); }",
    ".ow-send:active:not(:disabled) { transform: scale(.96); }",
    ".ow-send:disabled { opacity: .35; cursor: not-allowed; box-shadow: none; }",
    ".ow-send svg { width: 18px; height: 18px; }",
    ".ow-end { display: flex; justify-content: center; padding: 0 16px 12px; flex-shrink: 0; }",
    ".ow-end button { background: rgba(255,255,255,.03); border: 1px solid rgba(248,113,113,.25); color: #fca5a5; cursor: pointer; font-size: 12px; padding: 6px 12px; border-radius: 9999px; transition: all .15s ease; }",
    ".ow-end button:hover { background: rgba(220,38,38,.12); color: #fecaca; border-color: rgba(248,113,113,.45); }",
    ".ow-footer { padding: 0 16px 12px; text-align: center; flex-shrink: 0; }",
    ".ow-footer span { font-size: 10px; color: #6b5d8f; letter-spacing: .04em; }",
    ".ow-footer b { color: #a78bfa; font-weight: 600; }",
  ].join("\n");

  var ICON_LAUNCHER =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.6 4.4L18 9l-4.4 1.6L12 15l-1.6-4.4L6 9l4.4-1.6L12 3z" fill="currentColor" fill-opacity=".95" stroke="none"/><path d="M19 14l.7 1.9L21.5 16.6 19.7 17.3 19 19.2 18.3 17.3 16.5 16.6 18.3 15.9 19 14z" fill="currentColor" fill-opacity=".85" stroke="none"/><path d="M5 15l.6 1.6L7.2 17.2 5.6 17.8 5 19.4 4.4 17.8 2.8 17.2 4.4 16.6 5 15z" fill="currentColor" fill-opacity=".75" stroke="none"/></svg>';
  var ICON_AVATAR =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.6 4.4L18 9l-4.4 1.6L12 15l-1.6-4.4L6 9l4.4-1.6L12 3z" fill="currentColor" stroke="none"/></svg>';
  var ICON_MIC =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0"/><path d="M12 18v3"/></svg>';
  var ICON_CHAT =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>';
  var ICON_SEND =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5"/><path d="M5 12l7-7 7 7"/></svg>';
  var ICON_X =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="16" height="16"><path d="M18 6L6 18"/><path d="M6 6l12 12"/></svg>';
  var ICON_CHEVRON =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="14" height="14"><polyline points="6 9 12 15 18 9"/></svg>';

  var LANG_FLAGS = {
    en: "🇺🇸", es: "🇪🇸", fr: "🇫🇷", de: "🇩🇪", it: "🇮🇹",
    pt: "🇧🇷", nl: "🇳🇱", sv: "🇸🇪", ro: "🇷🇴", ru: "🇷🇺",
    uk: "🇺🇦", pl: "🇵🇱", ar: "🇸🇦", tr: "🇹🇷", hi: "🇮🇳",
    bn: "🇧🇩", zh: "🇨🇳", ja: "🇯🇵", ko: "🇰🇷", id: "🇮🇩",
    vi: "🇻🇳", tl: "🇵🇭", sw: "🇰🇪", multi: "🌐", auto: "🌐",
  };

  var LANG_LABELS = {
    en: "English", es: "Spanish", fr: "French", de: "German", it: "Italian",
    pt: "Portuguese", nl: "Dutch", sv: "Swedish", ro: "Romanian", ru: "Russian",
    uk: "Ukrainian", pl: "Polish", ar: "Arabic", tr: "Turkish", hi: "Hindi",
    bn: "Bengali", zh: "Chinese", ja: "Japanese", ko: "Korean", id: "Indonesian",
    vi: "Vietnamese", tl: "Filipino", sw: "Swahili",
  };

  // Map full BCP-47 browser locales to Omniweb-supported language codes so
  // Auto-detect can resolve navigator.language → a single supported code.
  var BROWSER_LANG_MAP = {
    en: "en", "en-us": "en", "en-gb": "en", "en-ca": "en", "en-au": "en", "en-nz": "en", "en-ie": "en", "en-in": "en", "en-za": "en",
    es: "es", "es-mx": "es", "es-es": "es", "es-ar": "es", "es-cl": "es", "es-co": "es", "es-pe": "es", "es-us": "es", "es-419": "es",
    fr: "fr", "fr-fr": "fr", "fr-ca": "fr", "fr-be": "fr", "fr-ch": "fr",
    de: "de", "de-de": "de", "de-at": "de", "de-ch": "de",
    it: "it", "it-it": "it", "it-ch": "it",
    pt: "pt", "pt-br": "pt", "pt-pt": "pt",
    nl: "nl", "nl-nl": "nl", "nl-be": "nl",
    sv: "sv", "sv-se": "sv", "sv-fi": "sv",
    ro: "ro", "ro-ro": "ro",
    ru: "ru", "ru-ru": "ru", "ru-by": "ru", "ru-kz": "ru", "ru-ua": "ru",
    uk: "uk", "uk-ua": "uk",
    pl: "pl", "pl-pl": "pl",
    ar: "ar", "ar-sa": "ar", "ar-eg": "ar", "ar-ae": "ar", "ar-ma": "ar", "ar-jo": "ar", "ar-iq": "ar", "ar-ly": "ar",
    tr: "tr", "tr-tr": "tr",
    hi: "hi", "hi-in": "hi",
    bn: "bn", "bn-bd": "bn", "bn-in": "bn",
    zh: "zh", "zh-cn": "zh", "zh-tw": "zh", "zh-hk": "zh", "zh-sg": "zh", "zh-hans": "zh", "zh-hant": "zh",
    ja: "ja", "ja-jp": "ja",
    ko: "ko", "ko-kr": "ko",
    id: "id", "id-id": "id",
    vi: "vi", "vi-vn": "vi",
    tl: "tl", fil: "tl", "fil-ph": "tl", "tl-ph": "tl",
    sw: "sw", "sw-ke": "sw", "sw-tz": "sw",
  };

  function detectBrowserLanguage() {
    try {
      var candidates = [];
      if (window.navigator && navigator.languages && navigator.languages.length) {
        candidates = candidates.concat(Array.prototype.slice.call(navigator.languages));
      }
      if (window.navigator && navigator.language) candidates.push(navigator.language);
      for (var i = 0; i < candidates.length; i += 1) {
        var raw = String(candidates[i] || "").toLowerCase().replace("_", "-");
        if (!raw) continue;
        if (BROWSER_LANG_MAP[raw]) return BROWSER_LANG_MAP[raw];
        var base = raw.split("-")[0];
        if (BROWSER_LANG_MAP[base]) return BROWSER_LANG_MAP[base];
      }
    } catch (_) {}
    return "en";
  }

  function el(tag, opts) {
    var node = document.createElement(tag);
    if (!opts) return node;
    if (opts.className) node.className = opts.className;
    if (opts.text != null) node.textContent = opts.text;
    if (opts.html != null) node.innerHTML = opts.html;
    if (opts.attrs) {
      for (var k in opts.attrs) {
        if (Object.prototype.hasOwnProperty.call(opts.attrs, k)) {
          node.setAttribute(k, opts.attrs[k]);
        }
      }
    }
    return node;
  }

  function buildPanel(config) {
    var root = el("div", {
      className: "ow-root " + (config.position === "bottom-left" ? "left" : "right"),
    });

    var launcher = el("button", {
      className: "ow-launcher",
      html: ICON_LAUNCHER,
      attrs: { type: "button", "aria-label": "Open AI assistant" },
    });

    var panel = el("div", { className: "ow-panel", attrs: { role: "dialog", "aria-label": "AI assistant" } });

    var header = el("div", { className: "ow-header" });
    var avatar = el("div", { className: "ow-avatar", html: ICON_AVATAR });
    var titleWrap = el("div", { className: "ow-title" });
    var titleName = el("p", { className: "ow-title-name", text: config.businessName || "Omniweb AI" });
    var titleSub = el("p", { className: "ow-title-sub" });
    var statusDot = el("span", { className: "ow-status-dot" });
    var statusText = el("span", { text: "Ready to help" });
    titleSub.appendChild(statusDot);
    titleSub.appendChild(statusText);
    titleWrap.appendChild(titleName);
    titleWrap.appendChild(titleSub);
    var closeBtn = el("button", { className: "ow-close", html: ICON_X, attrs: { type: "button", "aria-label": "Close" } });
    header.appendChild(avatar);
    header.appendChild(titleWrap);
    header.appendChild(closeBtn);

    var transcript = el("div", { className: "ow-transcript" });
    var empty = el("p", {
      className: "ow-empty",
      text: "Ask anything — start a voice call or type a message below.",
    });
    transcript.appendChild(empty);

    var langSection = el("div", { className: "ow-lang" });
    var langLabel = el("div", { className: "ow-lang-label", text: "Language" });
    var langMenu = el("div", { className: "ow-lang-menu" });
    var langBtn = el("button", { className: "ow-lang-btn", attrs: { type: "button" } });
    var langBtnLabel = el("span", { html: '<span style="font-size:18px;line-height:1">🌐</span> <span class="ow-lang-name">English</span>' });
    var langBtnChev = el("span", { html: ICON_CHEVRON });
    langBtnLabel.style.display = "flex";
    langBtnLabel.style.alignItems = "center";
    langBtnLabel.style.gap = "8px";
    langBtn.appendChild(langBtnLabel);
    langBtn.appendChild(langBtnChev);
    langMenu.appendChild(langBtn);
    langSection.appendChild(langLabel);
    langSection.appendChild(langMenu);

    var modes = el("div", { className: "ow-modes" });
    var voiceBtn = el("button", {
      className: "ow-mode voice active",
      html: ICON_MIC + " Voice call",
      attrs: { type: "button" },
    });
    var textBtn = el("button", {
      className: "ow-mode text",
      html: ICON_CHAT + " Text chat",
      attrs: { type: "button" },
    });
    modes.appendChild(voiceBtn);
    modes.appendChild(textBtn);

    var compose = el("div", { className: "ow-compose" });
    var composeWrap = el("div", { className: "ow-compose-wrap" });
    var input = el("textarea", {
      className: "ow-input",
      attrs: { rows: "1", placeholder: "Type a message…" },
    });
    var sendBtn = el("button", {
      className: "ow-send",
      html: ICON_SEND,
      attrs: { type: "button", "aria-label": "Send message", title: "Send" },
    });
    composeWrap.appendChild(input);
    composeWrap.appendChild(sendBtn);
    compose.appendChild(composeWrap);

    var endRow = el("div", { className: "ow-end", attrs: { style: "display:none" } });
    var endBtn = el("button", { text: "End voice session", attrs: { type: "button" } });
    endRow.appendChild(endBtn);

    var footer = el("div", { className: "ow-footer" });
    var footerSpan = el("span", { html: "Powered by <b>Omniweb AI</b>" });
    footer.appendChild(footerSpan);

    panel.appendChild(header);
    panel.appendChild(transcript);
    panel.appendChild(langSection);
    panel.appendChild(modes);
    panel.appendChild(compose);
    panel.appendChild(endRow);
    panel.appendChild(footer);

    root.appendChild(launcher);
    root.appendChild(panel);

    return {
      root: root,
      launcher: launcher,
      panel: panel,
      statusText: statusText,
      statusDot: statusDot,
      closeBtn: closeBtn,
      transcript: transcript,
      empty: empty,
      langBtn: langBtn,
      langBtnName: langBtnLabel.querySelector(".ow-lang-name"),
      langMenu: langMenu,
      voiceBtn: voiceBtn,
      textBtn: textBtn,
      input: input,
      sendBtn: sendBtn,
      endRow: endRow,
      endBtn: endBtn,
    };
  }

  // ---------- mount ----------------------------------------------------------

  function mount(config) {
    var host = document.createElement("div");
    host.setAttribute("data-omniweb-widget-host", "true");
    document.body.appendChild(host);
    var root = host.attachShadow ? host.attachShadow({ mode: "open" }) : host;

    var style = document.createElement("style");
    style.textContent = STYLES;
    root.appendChild(style);

    var ui = buildPanel(config);
    root.appendChild(ui.root);

    var sessionId = getSessionId();
    var panelOpen = false;
    var mode = "voice"; // "voice" | "text"
    var voiceSession = null;
    var connecting = false;
    var sendingText = false;
    var languages = [];
    var configuredDefault = (config.defaultLanguage || "auto").toLowerCase();
    var rawConfiguredSupported = (config.supportedLanguages || []).map(function (c) {
      return String(c || "").toLowerCase();
    }).filter(Boolean);
    // "multi" / "auto" are not real language codes — they signal that the
    // shop wants automatic detection over the full supported set, so don't
    // use them to filter the picker.
    var configuredSupported = rawConfiguredSupported.filter(function (c) {
      return c !== "multi" && c !== "auto" && c !== "all";
    });
    var configuredAutoOnly =
      rawConfiguredSupported.length === 0 ||
      rawConfiguredSupported.indexOf("multi") >= 0 ||
      rawConfiguredSupported.indexOf("auto") >= 0 ||
      rawConfiguredSupported.indexOf("all") >= 0;
    var detectedBrowserLanguage = detectBrowserLanguage();
    var AUTO_LANG = { code: "auto", label: "Auto (detect language)", flag: "🌐", auto: true };
    var lastTurn = { role: null, content: "", bubble: null, body: null, finalizedAt: 0 };
    var WELCOME_FLAG_KEY = "omniweb_welcome_seen_" + (publicWidgetId || "default");
    var welcomeShownThisSession = false;

    function initialSelectedLang() {
      // Default to Auto whenever multi/auto is configured or more than one
      // language is supported. Only lock to a single language when the shop
      // explicitly enabled exactly one specific language.
      if (configuredAutoOnly) return AUTO_LANG;
      if (configuredSupported.length === 1) {
        var only = configuredSupported[0];
        return {
          code: only,
          label: LANG_LABELS[only] || only.toUpperCase(),
          flag: LANG_FLAGS[only] || "🌐",
        };
      }
      if (configuredDefault === "auto" || configuredDefault === "multi" || configuredSupported.length !== 1) {
        return AUTO_LANG;
      }
      return {
        code: configuredDefault,
        label: LANG_LABELS[configuredDefault] || configuredDefault.toUpperCase(),
        flag: LANG_FLAGS[configuredDefault] || "🌐",
      };
    }
    var selectedLang = initialSelectedLang();

    function setSubtitle(text, color) {
      ui.statusText.textContent = text;
      if (color) ui.statusDot.style.background = color;
      else ui.statusDot.style.background = "#22c55e";
    }

    function refreshSubtitle() {
      if (connecting) return setSubtitle("Connecting…", "#f59e0b");
      if (voiceSession && mode === "voice") return setSubtitle("Listening…", "#22d3ee");
      if (mode === "text") return setSubtitle("Type a message", "#a78bfa");
      setSubtitle("Ready to help");
    }

    function clearTranscript() {
      ui.transcript.innerHTML = "";
      ui.transcript.appendChild(ui.empty);
    }

    function removeEmptyState() {
      if (ui.empty.parentNode === ui.transcript) {
        ui.transcript.removeChild(ui.empty);
      }
    }

    function addBubble(role, content) {
      var text = String(content || "").trim();
      if (!text) return;
      removeEmptyState();
      var bubble = el("div", { className: "ow-msg " + (role === "user" ? "user" : "assistant") });
      bubble.setAttribute("data-content", text);
      var roleTag = el("p", { className: "ow-role", text: role === "user" ? "You" : "Assistant" });
      var body = el("p", { text: text });
      body.style.margin = "0";
      bubble.appendChild(roleTag);
      bubble.appendChild(body);
      ui.transcript.appendChild(bubble);
      ui.transcript.scrollTop = ui.transcript.scrollHeight;
      lastTurn = { role: role, content: text, bubble: bubble, body: body, finalizedAt: Date.now() };
    }

    function addBookingAction(bookingUrl) {
      var url = String(bookingUrl || "").trim();
      if (!url) return;
      removeEmptyState();
      var wrap = el("div", { className: "ow-booking-action" });
      var btn = el("button", {
        className: "ow-booking-btn",
        text: "Book Appointment",
        attrs: { type: "button" },
      });
      btn.addEventListener("click", function () {
        try {
          window.open(url, "_blank", "noopener,noreferrer");
        } catch (_) {
          window.location.href = url;
        }
      });
      wrap.appendChild(btn);
      ui.transcript.appendChild(wrap);
      ui.transcript.scrollTop = ui.transcript.scrollHeight;
    }

    var GREETING_PATTERN = /^(welcome|hello|hi|hey|good (morning|afternoon|evening)|greetings|hola|bonjour|hallo|ciao|olá|olaaa|namaste|salaam|salam|salom|你好|こんにちは|안녕)/i;

    function looksLikeGreeting(text) {
      return GREETING_PATTERN.test((text || "").trim().slice(0, 60));
    }

    // Merge consecutive ConversationText events from the same role into one
    // bubble. Deepgram streams partial → full assistant text in multiple
    // events, sometimes re-emits the same final text, and occasionally emits
    // a second LLM-generated greeting variant on top of its TTS greeting.
    function applyTranscript(role, content) {
      var text = String(content || "").trim();
      if (!text) return;

      // Per-session welcome dedupe: once we have an assistant greeting, drop
      // any second assistant message that also looks like a greeting until a
      // user message arrives. This kills the "Welcome! I am Sandy…" + "Welcome!
      // I'm here to answer questions…" duplicate from voice mode.
      if (role === "assistant" && looksLikeGreeting(text)) {
        if (welcomeShownThisSession && (!lastTurn.role || lastTurn.role === "assistant")) {
          return;
        }
        welcomeShownThisSession = true;
        try { window.localStorage.setItem(WELCOME_FLAG_KEY, "1"); } catch (_) {}
      }
      if (role === "user") {
        // A real user turn re-arms greeting dedupe for legitimate follow-ups.
        welcomeShownThisSession = true;
      }

      var SAME_TURN_MS = 8000;
      var canMerge =
        lastTurn.bubble &&
        lastTurn.role === role &&
        lastTurn.body &&
        Date.now() - lastTurn.finalizedAt < SAME_TURN_MS;
      if (canMerge) {
        var prev = lastTurn.content;
        if (text === prev) return;
        if (text.length > prev.length && text.indexOf(prev) === 0) {
          lastTurn.body.textContent = text;
          lastTurn.bubble.setAttribute("data-content", text);
          lastTurn.content = text;
          lastTurn.finalizedAt = Date.now();
          ui.transcript.scrollTop = ui.transcript.scrollHeight;
          return;
        }
        if (prev.length > text.length && prev.indexOf(text) === 0) {
          return;
        }
        if (prev.indexOf(text) >= 0) return;
        if (role === "assistant" && looksLikeGreeting(prev) && looksLikeGreeting(text)) {
          // Both look like greetings — treat as same turn variant, keep the
          // longer one and drop the duplicate variant.
          if (text.length > prev.length) {
            lastTurn.body.textContent = text;
            lastTurn.bubble.setAttribute("data-content", text);
            lastTurn.content = text;
            lastTurn.finalizedAt = Date.now();
          }
          return;
        }
        var combined = (prev + " " + text).replace(/\s+/g, " ").trim();
        lastTurn.body.textContent = combined;
        lastTurn.bubble.setAttribute("data-content", combined);
        lastTurn.content = combined;
        lastTurn.finalizedAt = Date.now();
        ui.transcript.scrollTop = ui.transcript.scrollHeight;
        return;
      }
      addBubble(role, text);
    }

    function showError(message) {
      removeEmptyState();
      var prev = ui.transcript.querySelector(".ow-error");
      if (prev && prev.parentNode) prev.parentNode.removeChild(prev);
      var box = el("div", { className: "ow-error" });
      var span = el("span", { text: message });
      var retry = el("button", { text: "Retry", attrs: { type: "button" } });
      retry.addEventListener("click", function () {
        if (box.parentNode) box.parentNode.removeChild(box);
        if (mode === "voice") startVoice();
        else startText();
      });
      box.appendChild(span);
      box.appendChild(retry);
      ui.transcript.appendChild(box);
      ui.transcript.scrollTop = ui.transcript.scrollHeight;
    }

    function openPanel() {
      if (panelOpen) return;
      panelOpen = true;
      ui.panel.classList.add("open");
      track("widget_opened", {});
    }

    function closePanel() {
      panelOpen = false;
      ui.panel.classList.remove("open");
      stopSession();
    }

    function setActiveMode(next) {
      mode = next;
      ui.voiceBtn.classList.toggle("active", next === "voice");
      ui.textBtn.classList.toggle("active", next === "text");
      refreshSubtitle();
    }

    function isAutoLang() {
      return !!(selectedLang && (selectedLang.auto || selectedLang.code === "auto"));
    }

    // Priority order: manual selection > Auto resolved to detected browser
    // language > existing detection > English fallback.
    function effectiveLanguageCode() {
      if (!selectedLang) return detectedBrowserLanguage || "en";
      if (isAutoLang()) return detectedBrowserLanguage || "en";
      return selectedLang.code || "en";
    }

    function languagePayload() {
      return {
        language: effectiveLanguageCode(),
        languageMode: isAutoLang() ? "auto" : "manual",
        detectedLanguage: detectedBrowserLanguage,
      };
    }

    function bootstrapVoice() {
      var lp = languagePayload();
      var body = {
        language: lp.language,
        language_mode: lp.languageMode,
        detected_language: lp.detectedLanguage,
        widget_key: publicWidgetId,
        public_widget_key: publicWidgetId,
      };
      return request("/api/chat/voice-agent/bootstrap", body);
    }

    function completeVoiceSession(session) {
      var meta = session && session.sessionComplete;
      if (!meta || meta.sent || !meta.clientId || !meta.transcript || !meta.transcript.length) {
        return Promise.resolve();
      }
      meta.sent = true;
      return request("/api/chat/voice-agent/session-complete", {
        client_id: meta.clientId,
        language: meta.language,
        mode: "voice",
        started_at: meta.startedAt,
        ended_at: new Date().toISOString(),
        transcript: meta.transcript,
      })
        .then(function (result) {
          if (result && result.email_status) {
            track("email_request_sent", { provider: "deepgram", email_status: result.email_status });
          }
          return result;
        })
        .catch(function () {});
    }

    function startSession(withMic) {
      if (connecting) return Promise.resolve();
      connecting = true;
      refreshSubtitle();
      return stopSession()
        .then(bootstrapVoice)
        .then(function (payload) {
          var lp = languagePayload();
          var voiceTranscript = [];
          var session = new VoiceSession({
            onTranscript: function (line) {
              if (line && line.content) {
                voiceTranscript.push({
                  role: line.role,
                  content: line.content,
                  timestamp: new Date().toISOString(),
                });
              }
              applyTranscript(line.role, line.content);
            },
            onError: function (m) { showError(m); },
            onClose: function () {
              completeVoiceSession(session);
              voiceSession = null;
              connecting = false;
              ui.endRow.style.display = "none";
              refreshSubtitle();
            },
          });
          session.sessionComplete = {
            clientId: payload.client_id,
            language: lp.language,
            startedAt: new Date().toISOString(),
            transcript: voiceTranscript,
            sent: false,
          };
          return session
            .connect({
              websocketUrl: payload.websocket_url,
              accessToken: payload.access_token,
              settings: payload.settings,
              enableMic: !!withMic,
            })
            .then(function () {
              voiceSession = session;
              connecting = false;
              ui.endRow.style.display = withMic ? "flex" : "none";
              refreshSubtitle();
              track(withMic ? "voice_started" : "message_sent", {
                provider: "deepgram",
                client_id: payload.client_id,
              });
            });
        })
        .catch(function (e) {
          connecting = false;
          var msg = (e && e.message) || "Failed to connect";
          showError(msg);
          return stopSession();
        });
    }

    function stopSession() {
      var s = voiceSession;
      voiceSession = null;
      ui.endRow.style.display = "none";
      if (s) {
        return s.disconnect().catch(function () {}).then(function () {
          return completeVoiceSession(s);
        });
      }
      return Promise.resolve();
    }

    function startVoice() {
      setActiveMode("voice");
      openPanel();
      return startSession(true);
    }

    function startText() {
      setActiveMode("text");
      openPanel();
      // Text chat uses the REST endpoint — make sure any active voice
      // websocket (with TTS playback) is fully torn down so typing
      // doesn't trigger spoken responses or duplicate transcripts.
      return stopSession();
    }

    function looksLikeScheduleIntent(text) {
      return /(book|schedule|appointment|consultation|demo|call me|contact me|need service)/i.test(text || "");
    }

    function showThinking(label) {
      removeEmptyState();
      var existing = ui.transcript.querySelector(".ow-msg.assistant.ow-thinking");
      if (existing) return existing;
      var bubble = el("div", { className: "ow-msg assistant ow-thinking" });
      var roleTag = el("p", { className: "ow-role", text: "Assistant" });
      var dots = label
        ? el("p", { text: label })
        : el("p", {
            className: "ow-typing",
            html: "<span></span><span></span><span></span>",
          });
      dots.style.margin = "0";
      bubble.appendChild(roleTag);
      bubble.appendChild(dots);
      ui.transcript.appendChild(bubble);
      ui.transcript.scrollTop = ui.transcript.scrollHeight;
      return bubble;
    }

    function clearThinking() {
      var existing = ui.transcript.querySelector(".ow-msg.assistant.ow-thinking");
      if (existing && existing.parentNode) existing.parentNode.removeChild(existing);
    }

    function setSending(flag) {
      sendingText = !!flag;
      ui.sendBtn.disabled = sendingText;
      ui.input.disabled = sendingText;
    }

    function chatRequestWithTimeout(payload, timeoutMs) {
      return new Promise(function (resolve, reject) {
        var done = false;
        var timer = setTimeout(function () {
          if (done) return;
          done = true;
          reject(new Error("Request timed out. Please try again."));
        }, timeoutMs || 15000);
        request("/api/widget/chat", payload).then(
          function (r) {
            if (done) return;
            done = true;
            clearTimeout(timer);
            resolve(r);
          },
          function (e) {
            if (done) return;
            done = true;
            clearTimeout(timer);
            reject(e);
          }
        );
      });
    }

    function sendText() {
      if (sendingText) return;
      var text = (ui.input.value || "").trim();
      if (!text) return;
      ui.input.value = "";

      // If a voice session is open AND the user is in voice mode, route
      // through the realtime agent (so it sees the same conversation
      // history). The agent will echo a ConversationText for the user
      // role, which renders the bubble — so do NOT pre-add it locally
      // (that's what was causing the "doubled input" bug).
      if (mode === "voice" && voiceSession) {
        try {
          voiceSession.injectUserMessage(text);
          return;
        } catch (_) { /* fall through to REST */ }
      }

      // Default text-chat path: REST request, no voice playback.
      setActiveMode("text");
      applyTranscript("user", text);
      showThinking(looksLikeScheduleIntent(text) ? "Preparing booking link…" : null);
      setSending(true);
      var lp = languagePayload();
      chatRequestWithTimeout({
        publicWidgetId: publicWidgetId,
        sessionId: sessionId,
        message: text,
        language: lp.language,
        languageMode: lp.languageMode,
        detectedLanguage: lp.detectedLanguage,
        domain: window.location.hostname,
        pageUrl: window.location.href,
      }, 20000)
        .then(function (response) {
          clearThinking();
          setSending(false);
          var content =
            response &&
            response.data &&
            response.data.message &&
            typeof response.data.message.content === "string"
              ? response.data.message.content.trim()
              : "";
          if (content) {
            applyTranscript("assistant", content);
            var actions = (response && response.data && response.data.actions) || [];
            for (var i = 0; i < actions.length; i += 1) {
              var action = actions[i] || {};
              var payload = action.payload || {};
              if (action.type === "schedule_appointment" && payload.bookingUrl) {
                addBookingAction(payload.bookingUrl);
              }
            }
          } else {
            applyTranscript(
              "assistant",
              "I'm sorry — I had trouble responding. Please try again."
            );
          }
        })
        .catch(function (e) {
          clearThinking();
          setSending(false);
          var msg = (e && e.message) || "Sorry — something went wrong. Please try again.";
          showError(msg);
          if (typeof console !== "undefined" && console.warn) {
            console.warn("[Omniweb] widget chat failed:", msg);
          }
        });
    }

    function loadLanguages() {
      getJson("/api/chat/languages")
        .then(function (data) {
          var list = (data && data.languages) || [];
          if (!list.length) return;

          // Decorate each language with a label + flag so the picker has a
          // complete display set even when the API omits them.
          var decorated = list.map(function (l) {
            var code = String(l.code || "").toLowerCase();
            return {
              code: code,
              label: l.label || LANG_LABELS[code] || code.toUpperCase(),
              flag: l.flag || LANG_FLAGS[code] || "🌐",
            };
          }).filter(function (l) { return l.code; });

          // Always expose Auto + every supported language so visitors can
          // switch freely. The shop's configuredSupported list controls the
          // *default* selection, not what the picker offers — locking the
          // picker to a single row leaves the visitor with nothing to pick
          // and the dropdown looks broken.
          languages = [AUTO_LANG].concat(decorated);

          var initial = AUTO_LANG;
          if (configuredAutoOnly) {
            initial = AUTO_LANG;
          } else if (configuredSupported.length === 1) {
            // Single specific language configured — pre-select it but still
            // let the visitor switch to any other language from the menu.
            for (var i = 0; i < decorated.length; i += 1) {
              if (decorated[i].code === configuredSupported[0]) {
                initial = decorated[i];
                break;
              }
            }
          } else {
            for (var j = 0; j < decorated.length; j += 1) {
              if (decorated[j].code === configuredDefault) {
                initial = decorated[j];
                break;
              }
            }
          }
          selectedLang = initial;
          renderLangButton();
        })
        .catch(function () { /* keep defaults */ });
    }

    function renderLangButton() {
      var flag = (selectedLang && selectedLang.flag) || LANG_FLAGS[selectedLang.code] || "🌐";
      ui.langBtn.firstChild.firstChild.textContent = flag;
      ui.langBtnName.textContent = selectedLang.label || selectedLang.code;
    }

    function toggleLangMenu() {
      var existing = ui.langMenu.querySelector(".ow-lang-list");
      if (existing) {
        ui.langMenu.removeChild(existing);
        return;
      }
      if (!languages.length) return;
      var list = document.createElement("ul");
      list.className = "ow-lang-list";
      for (var i = 0; i < languages.length; i += 1) {
        (function (lang) {
          var li = document.createElement("li");
          var btn = document.createElement("button");
          btn.type = "button";
          btn.innerHTML =
            '<span style="font-size:16px;line-height:1">' +
            ((lang.flag || LANG_FLAGS[lang.code] || "🌐")) +
            "</span><span>" +
            (lang.label || lang.code) +
            "</span>";
          btn.addEventListener("click", function () {
            selectedLang = lang;
            renderLangButton();
            list.parentNode && list.parentNode.removeChild(list);
          });
          li.appendChild(btn);
          list.appendChild(li);
        })(languages[i]);
      }
      ui.langMenu.appendChild(list);
    }

    // Wire events
    ui.launcher.addEventListener("click", function () {
      if (panelOpen) closePanel();
      else { openPanel(); refreshSubtitle(); }
    });
    ui.closeBtn.addEventListener("click", closePanel);
    ui.voiceBtn.addEventListener("click", function () { startVoice(); });
    ui.textBtn.addEventListener("click", function () { startText(); });
    ui.sendBtn.addEventListener("click", sendText);
    ui.input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendText();
      }
    });
    ui.langBtn.addEventListener("click", toggleLangMenu);
    ui.endBtn.addEventListener("click", function () {
      stopSession();
      track("voice_ended", {});
    });

    // Hide voice features if disabled by tenant config
    if (config.voiceEnabled === false) {
      ui.voiceBtn.style.display = "none";
      ui.endRow.style.display = "none";
      setActiveMode("text");
    }

    // Initial UI state. The voice agent delivers its own configured greeting;
    // pre-rendering it here causes the welcome message to appear twice.
    try {
      welcomeShownThisSession = window.localStorage.getItem(WELCOME_FLAG_KEY) === "1";
    } catch (_) { welcomeShownThisSession = false; }
    renderLangButton();
    refreshSubtitle();
    loadLanguages();
    installPing();
    track("widget_loaded", { path: window.location.pathname });
  }

  // ---------- boot -----------------------------------------------------------

  request("/api/widget/handshake", {
    publicWidgetId: publicWidgetId,
    domain: window.location.hostname,
    pageUrl: window.location.href,
    referrer: document.referrer || null,
  })
    .then(function (payload) {
      if (!payload || payload.success !== true || !payload.data) {
        console.warn("[Omniweb] Widget handshake blocked.");
        return;
      }
      mount(payload.data);
    })
    .catch(function (err) {
      console.warn("[Omniweb] Widget handshake blocked.", err && err.message);
    });
})();

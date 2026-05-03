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
                  var pcm = float32To16kHzPcm(ch, inRate);
                  if (pcm.byteLength) self._sendBinary(pcm);
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
    for (var i = 0; i < this.scheduledSources.length; i += 1) {
      try { this.scheduledSources[i].stop(); } catch (_) {}
    }
    this.scheduledSources = [];
    if (this.ttsContext) this.playHead = this.ttsContext.currentTime;
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
    if (data.type === "UserStartedSpeaking") this._stopPlayback();
    if (data.type === "AgentStartedSpeaking" && this.handlers.onAgentSpeaking) {
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
    ":host, * { box-sizing: border-box; }",
    ":host { all: initial; font-family: 'Inter', system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; -webkit-text-size-adjust: 100%; text-size-adjust: 100%; }",
    ".ow-root { position: fixed; z-index: 2147483647; bottom: 24px; }",
    ".ow-root.right { right: 24px; }",
    ".ow-root.left { left: 24px; }",
    ".ow-launcher { width: 64px; height: 64px; border-radius: 9999px; border: 0; cursor: pointer; padding: 0; background: conic-gradient(from 200deg at 50% 50%, #0ea5e9 0deg, #e0f2fe 80deg, #0369a1 200deg, #7dd3fc 320deg, #0ea5e9 360deg); box-shadow: 0 8px 28px rgba(56,189,248,0.4), inset 0 2px 10px rgba(255,255,255,0.32), 0 0 0 1px rgba(255,255,255,0.1); transition: transform .15s ease; }",
    ".ow-launcher:hover { transform: scale(1.05); }",
    ".ow-launcher:active { transform: scale(.96); }",
    ".ow-panel { display: none; position: fixed; z-index: 2147483646; right: 24px; bottom: 100px; width: 360px; max-width: calc(100vw - 24px); height: min(640px, calc(100dvh - 120px)); max-height: calc(100dvh - 120px); border-radius: 18px; overflow: hidden; background: #0b1220; color: #e2e8f0; border: 1px solid rgba(255,255,255,0.08); box-shadow: 0 24px 60px rgba(2,6,23,.5); flex-direction: column; font-size: 14px; line-height: 1.4; }",
    ".ow-root.left .ow-panel { left: 24px; right: auto; }",
    "@media (max-width: 480px) { .ow-panel { right: 12px; left: 12px; bottom: 96px; width: auto; max-width: none; height: calc(100dvh - 120px); max-height: calc(100dvh - 120px); } .ow-root.left .ow-panel { left: 12px; right: 12px; } }",
    ".ow-panel.open { display: flex; }",
    ".ow-header { display: flex; align-items: center; gap: 12px; padding: 16px 16px 12px; border-bottom: 1px solid rgba(255,255,255,0.06); flex-shrink: 0; }",
    ".ow-avatar { width: 40px; height: 40px; border-radius: 9999px; flex-shrink: 0; background: conic-gradient(from 210deg at 50% 50%, #38bdf8, #f8fafc, #0284c7, #38bdf8); box-shadow: inset 0 1px 6px rgba(255,255,255,0.4); }",
    ".ow-title { flex: 1; min-width: 0; }",
    ".ow-title-name { font-size: 14px; font-weight: 600; color: #f8fafc; line-height: 1.2; margin: 0; }",
    ".ow-title-sub { font-size: 12px; color: #94a3b8; margin-top: 2px; }",
    ".ow-close { background: transparent; border: 0; color: #94a3b8; cursor: pointer; padding: 6px; border-radius: 8px; line-height: 0; }",
    ".ow-close:hover { background: rgba(255,255,255,0.05); color: #fff; }",
    ".ow-transcript { flex: 1; min-height: 0; overflow-y: auto; overscroll-behavior: contain; -webkit-overflow-scrolling: touch; padding: 12px 16px; display: flex; flex-direction: column; gap: 8px; }",
    ".ow-empty { color: #64748b; font-size: 12px; line-height: 1.6; padding: 4px 0; }",
    ".ow-error { background: rgba(127,29,29,.5); border: 1px solid rgba(248,113,113,.3); color: #fecaca; font-size: 12px; line-height: 1.4; border-radius: 10px; padding: 8px 10px; }",
    ".ow-error button { margin-top: 4px; background: transparent; border: 0; color: #fca5a5; cursor: pointer; font-size: 12px; text-decoration: underline; padding: 0; }",
    ".ow-msg { border-radius: 10px; padding: 8px 12px; font-size: 14px; line-height: 1.4; word-wrap: break-word; overflow-wrap: anywhere; white-space: pre-wrap; }",
    ".ow-msg .ow-role { font-size: 10px; text-transform: uppercase; letter-spacing: .08em; opacity: .6; margin-bottom: 2px; }",
    ".ow-msg.user { background: rgba(30,41,59,.8); margin-left: 16px; color: #f1f5f9; }",
    ".ow-msg.assistant { background: rgba(8,47,73,.4); border: 1px solid rgba(34,211,238,.15); color: #ecfeff; margin-right: 16px; }",
    ".ow-lang { padding: 8px 16px 4px; flex-shrink: 0; }",
    ".ow-lang-label { font-size: 10px; text-transform: uppercase; letter-spacing: .12em; color: #64748b; margin-bottom: 4px; }",
    ".ow-lang-btn { width: 100%; display: flex; align-items: center; justify-content: space-between; gap: 8px; background: rgba(15,23,42,.85); border: 1px solid rgba(255,255,255,0.08); color: #e2e8f0; padding: 8px 12px; border-radius: 10px; font-size: 14px; cursor: pointer; text-align: left; }",
    ".ow-lang-btn:hover:not(:disabled) { background: rgba(15,23,42,1); }",
    ".ow-lang-btn:disabled { opacity: .5; cursor: not-allowed; }",
    ".ow-lang-menu { position: relative; }",
    ".ow-lang-list { position: absolute; bottom: calc(100% + 4px); left: 0; right: 0; max-height: 192px; overflow-y: auto; background: #0f172a; border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; padding: 4px 0; box-shadow: 0 16px 40px rgba(2,6,23,.6); list-style: none; margin: 0; z-index: 5; }",
    ".ow-lang-list li button { width: 100%; background: transparent; border: 0; color: #e2e8f0; padding: 8px 12px; font-size: 14px; text-align: left; cursor: pointer; display: flex; align-items: center; gap: 8px; }",
    ".ow-lang-list li button:hover { background: rgba(255,255,255,0.04); }",
    ".ow-modes { display: flex; gap: 8px; padding: 8px 16px; flex-shrink: 0; }",
    ".ow-mode { flex: 1; display: flex; align-items: center; justify-content: center; gap: 8px; padding: 12px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.08); background: rgba(15,23,42,.7); color: #cbd5e1; font-size: 14px; font-weight: 500; cursor: pointer; transition: all .15s ease; }",
    ".ow-mode:hover:not(:disabled) { background: rgba(30,41,59,.9); }",
    ".ow-mode.active.voice { background: #06b6d4; color: #0f172a; border-color: transparent; box-shadow: 0 0 24px rgba(34,211,238,0.35); }",
    ".ow-mode.active.text { background: #1e293b; color: #fff; border-color: rgba(255,255,255,0.15); }",
    ".ow-mode:disabled { opacity: .5; cursor: not-allowed; }",
    ".ow-mode svg { width: 16px; height: 16px; }",
    ".ow-compose { display: flex; align-items: flex-end; gap: 8px; padding: 12px 16px 16px; border-top: 1px solid rgba(255,255,255,0.05); flex-shrink: 0; }",
    ".ow-input { flex: 1; min-width: 0; resize: none; background: rgba(15,23,42,.85); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; color: #f1f5f9; padding: 10px 12px; font-family: inherit; font-size: 14px; line-height: 1.4; min-height: 44px; max-height: 96px; outline: none; }",
    ".ow-input::placeholder { color: #64748b; }",
    ".ow-input:focus { border-color: rgba(34,211,238,.5); }",
    ".ow-send { flex-shrink: 0; width: 44px; height: 44px; border-radius: 9999px; border: 0; background: #7c3aed; color: #fff; display: flex; align-items: center; justify-content: center; cursor: pointer; }",
    ".ow-send:hover:not(:disabled) { background: #8b5cf6; }",
    ".ow-send:disabled { opacity: .4; cursor: not-allowed; }",
    ".ow-end { display: flex; justify-content: center; padding: 0 16px 12px; flex-shrink: 0; }",
    ".ow-end button { background: transparent; border: 0; color: #94a3b8; cursor: pointer; font-size: 12px; text-decoration: underline; padding: 4px; }",
    ".ow-end button:hover { color: #e2e8f0; }",
  ].join("\n");

  var ICON_MIC =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0"/><path d="M12 18v3"/></svg>';
  var ICON_CHAT =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a8 8 0 1 1-3-6.245V3"/><path d="M3 21l2.5-3"/></svg>';
  var ICON_SEND =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="M13 6l6 6-6 6"/></svg>';
  var ICON_X =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="18" height="18"><path d="M18 6L6 18"/><path d="M6 6l12 12"/></svg>';
  var ICON_CHEVRON =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="14" height="14"><polyline points="6 9 12 15 18 9"/></svg>';

  var LANG_FLAGS = {
    en: "🇺🇸", es: "🇪🇸", fr: "🇫🇷", de: "🇩🇪", it: "🇮🇹",
    pt: "🇧🇷", ja: "🇯🇵", ko: "🇰🇷", zh: "🇨🇳", hi: "🇮🇳", multi: "🌐",
  };

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
      attrs: { type: "button", "aria-label": "Open Omniweb AI" },
    });

    var panel = el("div", { className: "ow-panel", attrs: { role: "dialog", "aria-label": "Omniweb AI" } });

    var header = el("div", { className: "ow-header" });
    var avatar = el("div", { className: "ow-avatar" });
    var titleWrap = el("div", { className: "ow-title" });
    var titleName = el("p", { className: "ow-title-name", text: config.businessName || "Omniweb AI" });
    var titleSub = el("p", { className: "ow-title-sub", text: "Ready to help" });
    titleWrap.appendChild(titleName);
    titleWrap.appendChild(titleSub);
    var closeBtn = el("button", { className: "ow-close", html: ICON_X, attrs: { type: "button", "aria-label": "Close" } });
    header.appendChild(avatar);
    header.appendChild(titleWrap);
    header.appendChild(closeBtn);

    var transcript = el("div", { className: "ow-transcript" });
    var empty = el("p", {
      className: "ow-empty",
      text: "Start voice or type below. Your conversation appears here in real time.",
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
    var input = el("textarea", {
      className: "ow-input",
      attrs: { rows: "2", placeholder: "Start voice or type a message…" },
    });
    var sendBtn = el("button", {
      className: "ow-send",
      html: ICON_SEND,
      attrs: { type: "button", "aria-label": "Send" },
    });
    compose.appendChild(input);
    compose.appendChild(sendBtn);

    var endRow = el("div", { className: "ow-end", attrs: { style: "display:none" } });
    var endBtn = el("button", { text: "End voice session", attrs: { type: "button" } });
    endRow.appendChild(endBtn);

    panel.appendChild(header);
    panel.appendChild(transcript);
    panel.appendChild(langSection);
    panel.appendChild(modes);
    panel.appendChild(compose);
    panel.appendChild(endRow);

    root.appendChild(launcher);
    root.appendChild(panel);

    return {
      root: root,
      launcher: launcher,
      panel: panel,
      titleSub: titleSub,
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
    var languages = [];
    var selectedLang = { code: "en", label: "English" };

    function setSubtitle(text) {
      ui.titleSub.textContent = text;
    }

    function refreshSubtitle() {
      if (connecting) return setSubtitle("Connecting…");
      if (voiceSession) return setSubtitle(mode === "voice" ? "Listening…" : "Type a message");
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
      removeEmptyState();
      var bubble = el("div", { className: "ow-msg " + (role === "user" ? "user" : "assistant") });
      var roleTag = el("p", { className: "ow-role", text: role === "user" ? "You" : "Assistant" });
      var body = el("p", { text: content });
      body.style.margin = "0";
      bubble.appendChild(roleTag);
      bubble.appendChild(body);
      ui.transcript.appendChild(bubble);
      ui.transcript.scrollTop = ui.transcript.scrollHeight;
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

    function bootstrapVoice() {
      var body = {
        language: (selectedLang && selectedLang.code) || "en",
        widget_key: publicWidgetId,
        public_widget_key: publicWidgetId,
      };
      return request("/api/chat/voice-agent/bootstrap", body);
    }

    function startSession(withMic) {
      if (connecting) return Promise.resolve();
      connecting = true;
      refreshSubtitle();
      return stopSession()
        .then(bootstrapVoice)
        .then(function (payload) {
          var session = new VoiceSession({
            onTranscript: function (line) {
              addBubble(line.role, line.content);
            },
            onError: function (m) { showError(m); },
            onClose: function () {
              voiceSession = null;
              connecting = false;
              ui.endRow.style.display = "none";
              refreshSubtitle();
            },
          });
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
      if (s) return s.disconnect().catch(function () {});
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
      if (!voiceSession) return startSession(false);
      return Promise.resolve();
    }

    function sendText() {
      var text = (ui.input.value || "").trim();
      if (!text) return;
      ui.input.value = "";
      setActiveMode("text");
      addBubble("user", text);

      // Prefer realtime injection through the open voice agent (so the agent
      // brain sees the same conversation history) but fall back to the
      // ``/api/widget/chat`` REST endpoint if the agent socket isn't ready.
      if (voiceSession) {
        try {
          voiceSession.injectUserMessage(text);
          return;
        } catch (_) { /* fallthrough */ }
      }
      request("/api/widget/chat", {
        publicWidgetId: publicWidgetId,
        sessionId: sessionId,
        message: text,
        domain: window.location.hostname,
        pageUrl: window.location.href,
      })
        .then(function (response) {
          var content =
            response &&
            response.data &&
            response.data.message &&
            response.data.message.content;
          if (content) addBubble("assistant", content);
        })
        .catch(function () {
          showError("Sorry — something went wrong. Please try again.");
        });
    }

    function loadLanguages() {
      getJson("/api/chat/languages")
        .then(function (data) {
          var list = (data && data.languages) || [];
          if (!list.length) return;
          languages = list;
          var def = list.find ? list.find(function (l) { return l.code === "en"; }) : null;
          if (!def) def = list[0];
          if (def) {
            selectedLang = def;
            renderLangButton();
          }
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

    // Initial UI state
    if (config.welcomeMessage) addBubble("assistant", config.welcomeMessage);
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

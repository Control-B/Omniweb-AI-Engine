/**
 * Omniweb Shopify Storefront Chat Widget
 *
 * Drop-in script for Shopify themes.  Embed via theme app extension or
 * manually with:
 *
 *   <script
 *     src="https://YOUR_ENGINE/static/omniweb-shopify-widget.js"
 *     data-shop="merchant-store.myshopify.com"
 *     defer
 *   ></script>
 */
;(function () {
  "use strict"

  if (window.OmniwebChat && window.OmniwebChat.__loaded) return

  /* ── Configuration ────────────────────────────────────────────── */
  const SCRIPT = document.currentScript
  const SHOP = SCRIPT?.getAttribute("data-shop") || window.Shopify?.shop || ""
  if (!SHOP) return console.warn("[Omniweb] data-shop attribute missing")

  const ENGINE =
    SCRIPT?.getAttribute("data-engine") ||
    new URL(SCRIPT?.src || "").origin
  const API = ENGINE.replace(/\/$/, "")
  const HIDE_LAUNCHER = SCRIPT?.getAttribute("data-hide-launcher") === "true"

  /* ── State ────────────────────────────────────────────────────── */
  let token = null
  let tokenExp = 0
  let clientId = null
  let sessionId = null
  let endpoints = {}
  let greeting = ""
  let minimised = true
  let voiceSession = null
  let voiceBusy = false
  let messages = []
  let sending = false

  const LANGUAGE_OPTIONS = [
    ["multi", "🌐 Auto"],
    ["en", "🇺🇸 English"],
    ["es", "🇪🇸 Spanish"],
    ["fr", "🇫🇷 French"],
    ["de", "🇩🇪 German"],
    ["it", "🇮🇹 Italian"],
    ["pt", "🇵🇹 Portuguese"],
    ["nl", "🇳🇱 Dutch"],
    ["ja", "🇯🇵 Japanese"],
    ["ko", "🇰🇷 Korean"],
    ["zh", "🇨🇳 Chinese"],
    ["hi", "🇮🇳 Hindi"],
    ["ar", "🇸🇦 Arabic"],
  ]
  let selectedLanguage = detectDefaultLanguage()

  /* ── Styles ───────────────────────────────────────────────────── */
  const STYLE = document.createElement("style")
  STYLE.textContent = `
    #omniweb-launcher{position:fixed;bottom:24px;right:24px;z-index:99999;
      min-width:92px;height:58px;border-radius:999px;border:1px solid rgba(255,255,255,.45);
      background:linear-gradient(135deg,#f9fafb 0%,#9ca3af 18%,#f8fafc 38%,#475569 62%,#f8fafc 100%);
      color:#0f172a;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:8px;
      padding:0 18px;font:800 13px/1 system-ui,sans-serif;letter-spacing:.02em;
      box-shadow:0 18px 45px rgba(15,23,42,.28),inset 0 1px 1px rgba(255,255,255,.9);
      transition:transform .18s,box-shadow .18s,filter .18s}
    #omniweb-launcher:hover{transform:translateY(-2px) scale(1.03);filter:saturate(1.08);
      box-shadow:0 22px 58px rgba(15,23,42,.34),inset 0 1px 1px rgba(255,255,255,.95)}
    #omniweb-launcher .omniweb-orb{width:22px;height:22px;border-radius:50%;
      background:radial-gradient(circle at 32% 25%,#fff 0 16%,#cbd5e1 17% 38%,#334155 72%,#020617 100%);
      box-shadow:inset 0 1px 2px rgba(255,255,255,.9),0 0 18px rgba(203,213,225,.72)}
    #omniweb-chat-window{position:fixed;bottom:96px;right:24px;z-index:99999;
      width:min(420px,calc(100vw - 24px));max-height:min(720px,calc(100dvh - 112px));border-radius:28px;
      background:linear-gradient(145deg,rgba(248,250,252,.98),rgba(148,163,184,.94) 46%,rgba(15,23,42,.98));
      border:1px solid rgba(255,255,255,.55);color:#0f172a;
      display:flex;flex-direction:column;overflow:hidden;
      box-shadow:0 30px 90px rgba(2,6,23,.38),inset 0 1px 1px rgba(255,255,255,.86);font-family:system-ui,sans-serif;
      transition:opacity .2s,transform .2s}
    #omniweb-chat-window.hidden{opacity:0;transform:translateY(16px) scale(.98);pointer-events:none}
    #omniweb-chat-header{background:rgba(2,6,23,.86);color:#fff;padding:14px 16px;
      display:grid;grid-template-columns:1fr auto auto;align-items:center;gap:10px}
    #omniweb-chat-header .omniweb-title{font-size:15px;font-weight:800;letter-spacing:.01em}
    #omniweb-language{border:1px solid rgba(255,255,255,.22);border-radius:999px;background:rgba(15,23,42,.88);
      color:#fff;padding:7px 26px 7px 10px;font:700 12px/1 system-ui,sans-serif}
    #omniweb-chat-close{width:34px;height:34px;border-radius:50%;background:rgba(255,255,255,.1);
      border:1px solid rgba(255,255,255,.14);color:#fff;cursor:pointer;font-size:20px;line-height:1}
    #omniweb-mode-row{display:grid;grid-template-columns:1fr 1fr;gap:8px;padding:10px 12px;background:rgba(15,23,42,.08)}
    .omniweb-mode{border:0;border-radius:999px;padding:10px 12px;cursor:pointer;
      background:rgba(255,255,255,.42);color:#334155;font:800 13px/1 system-ui,sans-serif}
    .omniweb-mode.active{background:#0f172a;color:#fff;box-shadow:0 10px 24px rgba(15,23,42,.25)}
    #omniweb-chat-messages{flex:1;overflow-y:auto;padding:14px;display:flex;
      flex-direction:column;gap:10px;min-height:220px;max-height:330px;background:rgba(255,255,255,.88)}
    .omniweb-msg{padding:10px 14px;border-radius:14px;max-width:82%;
      font-size:14px;line-height:1.45;word-wrap:break-word}
    .omniweb-msg.assistant{background:#eef2ff;color:#1e1e2e;align-self:flex-start;
      border-bottom-left-radius:4px}
    .omniweb-msg.shopper{background:#0f172a;color:#fff;align-self:flex-end;
      border-bottom-right-radius:4px}
    .omniweb-msg.system{background:#f9fafb;color:#64748b;font-size:12px;
      text-align:center;align-self:center}
    #omniweb-voice-panel{display:none;padding:12px 14px;background:rgba(15,23,42,.92);color:#e5e7eb}
    #omniweb-voice-panel.active{display:block}
    #omniweb-voice-panel .omniweb-voice-row{display:flex;align-items:center;gap:10px}
    #omniweb-voice-panel .omniweb-voice-status{flex:1;font-size:13px;color:#cbd5e1}
    #omniweb-voice-panel .omniweb-voice-title{font-weight:800;font-size:14px;color:#fff}
    #omniweb-voice-panel button{border:0;border-radius:999px;padding:9px 13px;cursor:pointer;
      font:800 12px/1 system-ui,sans-serif}
    #omniweb-voice-action{background:linear-gradient(135deg,#f8fafc,#94a3b8,#f8fafc);color:#0f172a}
    #omniweb-voice-transcript{margin-top:12px;max-height:150px;overflow:auto;display:flex;
      flex-direction:column;gap:8px}
    .omniweb-voice-line{font-size:13px;line-height:1.35;padding:8px 10px;border-radius:12px}
    .omniweb-voice-line.user{background:#312e81;color:#eef2ff;align-self:flex-end}
    .omniweb-voice-line.assistant{background:#172033;color:#e5e7eb;align-self:flex-start}
    #omniweb-chat-input-row{display:flex;border-top:1px solid rgba(15,23,42,.1);padding:10px;background:#fff}
    #omniweb-chat-input{flex:1;border:none;outline:none;padding:10px 12px;
      font-size:14px;background:transparent}
    #omniweb-chat-send{background:#0f172a;color:#fff;border:none;cursor:pointer;
      border-radius:10px;padding:8px 16px;font-size:14px;font-weight:600;
      transition:opacity .15s}
    #omniweb-chat-send:disabled{opacity:.5;cursor:default}
    @media(max-width:480px){#omniweb-chat-window{right:8px;left:8px;bottom:84px;width:auto}
      #omniweb-launcher{right:14px;bottom:16px}#omniweb-chat-header{grid-template-columns:1fr auto}}
  `
  document.head.appendChild(STYLE)

  /* ── DOM ──────────────────────────────────────────────────────── */
  const launcher = el("button", { id: "omniweb-launcher" })
  launcher.type = "button"
  launcher.setAttribute("aria-expanded", "false")
  launcher.innerHTML = `<span class="omniweb-orb"></span><span>Ask AI</span>`
  launcher.onclick = toggleChat

  const win = el("div", { id: "omniweb-chat-window", className: "hidden" })
  const header = el("div", { id: "omniweb-chat-header" })
  const languageOptions = LANGUAGE_OPTIONS.map(([value, label]) => (
    `<option value="${value}"${value === selectedLanguage ? " selected" : ""}>${label}</option>`
  )).join("")
  header.innerHTML = `
    <span class="omniweb-title">Omniweb AI</span>
    <select id="omniweb-language" aria-label="Assistant language">${languageOptions}</select>
    <button id="omniweb-chat-close" type="button" aria-label="Close">&times;</button>
  `
  const modeRow = el("div", { id: "omniweb-mode-row" })
  modeRow.innerHTML = `
    <button class="omniweb-mode active" id="omniweb-chat-mode" type="button">Text</button>
    <button class="omniweb-mode" id="omniweb-voice-mode" type="button">Voice</button>
  `

  const msgBox = el("div", { id: "omniweb-chat-messages" })
  const voicePanel = el("div", { id: "omniweb-voice-panel" })
  voicePanel.innerHTML = `
    <div class="omniweb-voice-row">
      <div>
        <div class="omniweb-voice-title">Live voice assistant</div>
        <div class="omniweb-voice-status" id="omniweb-voice-status">Choose a language, then start.</div>
      </div>
      <button id="omniweb-voice-action" type="button">Start</button>
    </div>
    <div id="omniweb-voice-transcript"></div>
  `
  const inputRow = el("div", { id: "omniweb-chat-input-row" })
  const input = el("input", {
    id: "omniweb-chat-input",
    placeholder: "Ask me anything...",
  })
  const sendBtn = el("button", {
    id: "omniweb-chat-send",
    textContent: "Send",
  })
  inputRow.append(input, sendBtn)
  win.append(header, modeRow, msgBox, voicePanel, inputRow)
  document.body.append(launcher, win)
  if (HIDE_LAUNCHER) {
    launcher.style.display = "none"
  }

  document.getElementById("omniweb-chat-close").onclick = toggleChat
  document.getElementById("omniweb-language").onchange = (event) => {
    selectedLanguage = event.target.value || "multi"
    if (voiceSession) {
      stopVoice().catch(() => {})
      setVoiceStatus("Language changed. Press Start to speak in the selected language.")
    }
  }
  document.getElementById("omniweb-chat-mode").onclick = () => setMode("chat")
  document.getElementById("omniweb-voice-mode").onclick = () => setMode("voice")
  document.getElementById("omniweb-voice-action").onclick = () => {
    if (voiceSession) stopVoice()
    else startVoice()
  }
  sendBtn.onclick = sendMessage
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  })

  /* ── Bootstrap ────────────────────────────────────────────────── */
  bootstrap()

  async function bootstrap() {
    try {
      const res = await fetch(
        `${API}/api/shopify/public/bootstrap?shop=${encodeURIComponent(SHOP)}`
      )
      if (!res.ok) return console.warn("[Omniweb] bootstrap failed", res.status)
      const data = await res.json()
      token = data.public_token
      tokenExp = Date.now() + 28 * 60 * 1000 // refresh 2 min early
      clientId = data.client_id || null
      endpoints = data.endpoints || {}
      greeting = data.greeting || "Hi! How can I help you today?"
      if (!data.assistant_enabled) {
        launcher.style.display = "none"
        win.classList.add("hidden")
        return
      }
    } catch (err) {
      console.error("[Omniweb] bootstrap error", err)
    }
  }

  /* ── Chat ─────────────────────────────────────────────────────── */
  function setChatOpen(open) {
    minimised = !open
    win.classList.toggle("hidden", minimised)
    launcher.setAttribute("aria-expanded", String(open))
    if (open && !sessionId) startSession()
    if (!open && voiceSession) stopVoice().catch(() => {})
  }

  function toggleChat() {
    setChatOpen(minimised)
  }

  function setMode(mode) {
    const voiceMode = mode === "voice"
    document.getElementById("omniweb-chat-mode").classList.toggle("active", !voiceMode)
    document.getElementById("omniweb-voice-mode").classList.toggle("active", voiceMode)
    voicePanel.classList.toggle("active", voiceMode)
    inputRow.style.display = voiceMode ? "none" : "flex"
    if (!voiceMode) input.focus()
  }

  function toggleVoice() {
    setChatOpen(true)
    setMode("voice")
    if (!voiceSession && !voiceBusy) startVoice()
  }

  async function closeVoice() {
    await stopVoice()
  }

  async function startVoice() {
    if (voiceBusy) return
    voiceBusy = true
    setVoiceStatus("Connecting...")
    try {
      await ensureToken()
      if (!token) throw new Error("Storefront token is unavailable")
      const ctx = buildContext()
      const res = await authedFetch(endpoints.voice_session || "/api/shopify/public/voice/session", {
        method: "POST",
        body: JSON.stringify({
          context: ctx,
          language: selectedLanguageValue(),
        }),
      })
      if (!res.ok) {
        const detail = await readError(res)
        throw new Error(detail || `Voice session failed (${res.status})`)
      }
      const data = await res.json()
      sessionId = data.voice_session_id || data.session_id || sessionId
      const session = new StorefrontVoiceSession({
        onTranscript(line) {
          appendVoiceLine(line.role, line.content)
          appendMsg(line.role === "user" ? "shopper" : "assistant", line.content)
        },
        onError(message) {
          setVoiceStatus(message || "Voice error")
        },
        onClose() {
          voiceSession = null
          voiceBusy = false
          setVoiceStatus("Ended")
          setVoiceAction("Start")
        },
      })
      voiceSession = session
      await session.connect({
        websocketUrl: data.websocket_url || data.websocketUrl || data.deepgram?.websocket_url,
        accessToken: data.access_token || data.accessToken || data.deepgram?.access_token,
        settings: data.settings || data.deepgram?.settings,
      })
      setVoiceStatus("Listening...")
      setVoiceAction("End")
    } catch (err) {
      console.error("[Omniweb] voice error", err)
      setVoiceStatus(err?.message || "Could not start voice")
      appendMsg("system", "Voice couldn't start. Please try again.")
      await stopVoice()
    } finally {
      voiceBusy = false
    }
  }

  async function stopVoice() {
    const current = voiceSession
    voiceSession = null
    if (current) await current.disconnect()
    setVoiceAction("Start")
  }

  async function startSession() {
    await ensureToken()
    try {
      const ctx = buildContext()
      const res = await authedFetch(endpoints.start_session || "/api/shopify/public/sessions", {
        method: "POST",
        body: JSON.stringify({ context: ctx }),
      })
      const data = await res.json()
      sessionId = data.session_id
      appendMsg("assistant", data.welcome_message || greeting)
    } catch (err) {
      appendMsg("system", "Couldn't start session. Please try again.")
      console.error("[Omniweb] session error", err)
    }
  }

  async function sendMessage() {
    const text = input.value.trim()
    if (!text || sending) return
    input.value = ""
    sending = true
    sendBtn.disabled = true

    appendMsg("shopper", text)
    await ensureToken()

    try {
      const url = (endpoints.send_message || "/api/shopify/public/sessions/{session_id}/reply").replace(
        "{session_id}",
        sessionId
      )
      const res = await authedFetch(url, {
        method: "POST",
        body: JSON.stringify({ message: text, context: buildContext() }),
      })
      const data = await res.json()
      appendMsg("assistant", data.message)

      if (data.navigate_to && data.action === "navigate_to_product") {
        appendAction("View product →", data.navigate_to)
      }
      if (data.navigate_to && data.action === "navigate_to_page") {
        appendAction("Go there →", data.navigate_to)
      }
      if (data.checkout_url && data.action === "navigate_to_checkout") {
        appendAction("Go to checkout →", data.checkout_url)
      }
    } catch (err) {
      appendMsg("system", "Something went wrong. Try again.")
      console.error("[Omniweb] reply error", err)
    } finally {
      sending = false
      sendBtn.disabled = false
      input.focus()
    }
  }

  /* ── Track browsing events ────────────────────────────────────── */
  function trackEvent(type, payload) {
    if (!sessionId || !token) return
    const url = (endpoints.track_event || "/api/shopify/public/sessions/{session_id}/events")
      .replace("{session_id}", sessionId) + `?shop=${encodeURIComponent(SHOP)}`
    authedFetch(url, {
      method: "POST",
      body: JSON.stringify({ events: [{ type, payload, timestamp: new Date().toISOString() }] }),
    }).catch(() => {})
  }

  // Auto-track page views
  let lastUrl = ""
  setInterval(() => {
    if (location.href !== lastUrl) {
      lastUrl = location.href
      trackEvent("page_view", { url: location.href, title: document.title })

      // Detect product pages
      const match = location.pathname.match(/\/products\/([^/?#]+)/)
      if (match) {
        const meta = window.ShopifyAnalytics?.meta?.product
        if (meta) {
          trackEvent("product_view", {
            product: {
              id: String(meta.id || ""),
              title: meta.title || "",
              handle: match[1],
              vendor: meta.vendor || "",
              product_type: meta.type || "",
              price: meta.price ? meta.price / 100 : null,
              url: location.href,
            },
          })
        }
      }
    }
  }, 1500)

  /* ── Helpers ──────────────────────────────────────────────────── */
  function detectDefaultLanguage() {
    const lang = (navigator.language || "en").toLowerCase().split("-")[0]
    return LANGUAGE_OPTIONS.some(([value]) => value === lang) ? lang : "multi"
  }

  function selectedLanguageValue() {
    return selectedLanguage || "multi"
  }

  function selectedLanguageLabel() {
    const match = LANGUAGE_OPTIONS.find(([value]) => value === selectedLanguageValue())
    return match ? match[1].replace(/^[^\w]+\\s*/, "") : selectedLanguageValue()
  }

  function buildContext() {
    const language = selectedLanguageValue()
    return {
      shop_domain: SHOP,
      storefront_session_id: sessionId,
      current_page_url: location.href,
      current_page_title: document.title,
      currency: window.Shopify?.currency?.active || "USD",
      shopper_locale: language,
      selected_language: language,
      selected_language_label: selectedLanguageLabel(),
    }
  }

  async function ensureToken() {
    if (token && Date.now() < tokenExp) return
    await bootstrap()
  }

  function authedFetch(url, opts = {}) {
    const fullUrl = url.startsWith("http") ? url : `${API}${url}`
    return fetch(fullUrl, {
      ...opts,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        ...(opts.headers || {}),
      },
    })
  }

  async function readError(res) {
    try {
      const data = await res.json()
      return data.detail || data.error || JSON.stringify(data)
    } catch {
      return res.text()
    }
  }

  function setVoiceStatus(text) {
    const node = document.getElementById("omniweb-voice-status")
    if (node) node.textContent = text
  }

  function setVoiceAction(text) {
    const node = document.getElementById("omniweb-voice-action")
    if (node) node.textContent = text
  }

  function appendVoiceLine(role, text) {
    if (!text) return
    const box = document.getElementById("omniweb-voice-transcript")
    if (!box) return
    const line = el("div", { className: `omniweb-voice-line ${role}` })
    line.textContent = text
    box.appendChild(line)
    box.scrollTop = box.scrollHeight
  }

  function audioContextClass() {
    return window.AudioContext || window.webkitAudioContext || null
  }

  function floatTo16kPcm(input, inputSampleRate) {
    if (!input.length) return new ArrayBuffer(0)
    const ratio = inputSampleRate / 16000
    const outLen = Math.max(1, Math.floor(input.length / ratio))
    const out = new Int16Array(outLen)
    for (let i = 0; i < outLen; i += 1) {
      const srcPos = i * ratio
      const i0 = Math.floor(srcPos)
      const i1 = Math.min(i0 + 1, input.length - 1)
      const frac = srcPos - i0
      const sample = (input[i0] || 0) * (1 - frac) + (input[i1] || 0) * frac
      out[i] = Math.min(1, Math.max(-1, sample)) * 0x7fff
    }
    return out.buffer
  }

  class StorefrontVoiceSession {
    constructor(handlers) {
      this.handlers = handlers || {}
      this.ws = null
      this.micContext = null
      this.ttsContext = null
      this.micSource = null
      this.processor = null
      this.ttsAnalyser = null
      this.pendingSettingsJson = null
      this.settingsApplied = false
      this.sources = new Set()
      this.playHead = 0
      this.welcomeTimer = null
    }

    async connect(params) {
      await this.disconnect()
      if (!params.websocketUrl || !params.accessToken || !params.settings) {
        throw new Error("Voice bootstrap payload is incomplete")
      }
      const socket = new WebSocket(params.websocketUrl, ["bearer", params.accessToken])
      socket.binaryType = "arraybuffer"
      await new Promise((resolve, reject) => {
        const to = setTimeout(() => reject(new Error("WebSocket connection timeout")), 12000)
        socket.addEventListener("open", () => {
          clearTimeout(to)
          resolve()
        }, { once: true })
        socket.addEventListener("error", () => {
          clearTimeout(to)
          reject(new Error("WebSocket connection failed"))
        }, { once: true })
      })

      const AudioCtx = audioContextClass()
      if (!AudioCtx) throw new Error("Web Audio API is not available")

      this.ws = socket
      this.pendingSettingsJson = JSON.stringify(params.settings)
      socket.addEventListener("message", this.onMessage)
      socket.addEventListener("close", () => this.handlers.onClose?.())
      this.welcomeTimer = setTimeout(() => {
        this.handlers.onError?.("Voice service did not send Welcome.")
      }, 12000)

      this.ttsContext = new AudioCtx({ latencyHint: "interactive", sampleRate: 48000 })
      this.ttsAnalyser = this.ttsContext.createAnalyser()
      this.ttsAnalyser.connect(this.ttsContext.destination)
      this.playHead = this.ttsContext.currentTime

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, sampleRate: 16000 },
      })
      this.micContext = new AudioCtx()
      await this.micContext.resume()
      this.micSource = this.micContext.createMediaStreamSource(stream)
      this.processor = this.micContext.createScriptProcessor(4096, 1, 1)
      this.micSource.connect(this.processor)
      this.processor.connect(this.micContext.destination)
      const inputRate = this.micContext.sampleRate
      this.processor.onaudioprocess = (ev) => {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN || !this.settingsApplied) return
        const pcm = floatTo16kPcm(ev.inputBuffer.getChannelData(0), inputRate)
        if (pcm.byteLength) this.ws.send(pcm)
      }
      await this.ttsContext.resume()
    }

    onMessage = (ev) => {
      if (ev.data instanceof ArrayBuffer) {
        if (this.settingsApplied) this.playPcm(ev.data)
        return
      }
      try {
        const data = JSON.parse(String(ev.data))
        if (data.type === "Welcome" && this.ws && this.pendingSettingsJson) {
          if (this.welcomeTimer) clearTimeout(this.welcomeTimer)
          this.welcomeTimer = null
          this.ws.send(this.pendingSettingsJson)
          this.pendingSettingsJson = null
        }
        if (data.type === "SettingsApplied") this.settingsApplied = true
        if (data.type === "UserStartedSpeaking") this.stopPlayback()
        if (data.type === "ConversationText" && (data.role === "user" || data.role === "assistant")) {
          this.handlers.onTranscript?.({ role: data.role, content: String(data.content || "") })
        }
        if (data.type === "Error") {
          this.handlers.onError?.(data.message || JSON.stringify(data.description || data))
        }
      } catch {
        // Ignore non-JSON websocket messages.
      }
    }

    playPcm(buf) {
      if (!this.ttsContext || !this.ttsAnalyser) return
      const samples = new Int16Array(buf)
      if (!samples.length) return
      const buffer = this.ttsContext.createBuffer(1, samples.length, 24000)
      const ch = buffer.getChannelData(0)
      for (let i = 0; i < samples.length; i += 1) ch[i] = samples[i] / 32768
      const src = this.ttsContext.createBufferSource()
      src.buffer = buffer
      src.connect(this.ttsAnalyser)
      const now = this.ttsContext.currentTime
      if (this.playHead < now) this.playHead = now
      src.addEventListener("ended", () => this.sources.delete(src))
      src.start(this.playHead)
      this.playHead += buffer.duration
      this.sources.add(src)
    }

    stopPlayback() {
      this.sources.forEach((src) => {
        try { src.stop() } catch {}
      })
      this.sources.clear()
      if (this.ttsContext) this.playHead = this.ttsContext.currentTime
    }

    async disconnect() {
      if (this.welcomeTimer) clearTimeout(this.welcomeTimer)
      this.welcomeTimer = null
      this.pendingSettingsJson = null
      this.settingsApplied = false
      if (this.ws) {
        try {
          this.ws.removeEventListener("message", this.onMessage)
          this.ws.close(1000, "client disconnect")
        } catch {}
        this.ws = null
      }
      this.stopPlayback()
      if (this.processor) {
        try { this.processor.disconnect() } catch {}
        this.processor = null
      }
      if (this.micSource) {
        try { this.micSource.disconnect() } catch {}
        this.micSource.mediaStream.getTracks().forEach((track) => track.stop())
        this.micSource = null
      }
      if (this.micContext) {
        try { await this.micContext.close() } catch {}
        this.micContext = null
      }
      if (this.ttsContext) {
        try { await this.ttsContext.close() } catch {}
        this.ttsContext = null
      }
      this.ttsAnalyser = null
    }
  }

  function appendMsg(role, text) {
    const div = el("div", { className: `omniweb-msg ${role}` })
    div.textContent = text
    msgBox.appendChild(div)
    msgBox.scrollTop = msgBox.scrollHeight
  }

  function appendAction(label, url) {
    const a = el("a", {
      className: "omniweb-msg assistant",
      textContent: label,
      href: url,
    })
    a.style.cssText = "text-decoration:underline;cursor:pointer;color:#6366f1;font-weight:600"
    msgBox.appendChild(a)
    msgBox.scrollTop = msgBox.scrollHeight
  }

  function el(tag, props) {
    const node = document.createElement(tag)
    Object.assign(node, props || {})
    return node
  }

  // Expose for theme-level integrations
  window.OmniwebChat = {
    __loaded: true,
    trackEvent,
    toggleChat,
    openChat: () => setChatOpen(true),
    closeChat: () => setChatOpen(false),
    openVoice: () => toggleVoice(),
    isOpen: () => !minimised,
  }
})()

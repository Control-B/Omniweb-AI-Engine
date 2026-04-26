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

  /* ── Configuration ────────────────────────────────────────────── */
  const SCRIPT = document.currentScript
  const SHOP = SCRIPT?.getAttribute("data-shop") || window.Shopify?.shop || ""
  if (!SHOP) return console.warn("[Omniweb] data-shop attribute missing")

  const ENGINE =
    SCRIPT?.getAttribute("data-engine") ||
    new URL(SCRIPT?.src || "").origin
  const API = ENGINE.replace(/\/$/, "")

  /* ── State ────────────────────────────────────────────────────── */
  let token = null
  let tokenExp = 0
  let clientId = null
  let sessionId = null
  let endpoints = {}
  let greeting = ""
  let minimised = true
  let voiceOpen = false
  let voiceSession = null
  let voiceBusy = false
  let messages = []
  let sending = false

  /* ── Styles ───────────────────────────────────────────────────── */
  const STYLE = document.createElement("style")
  STYLE.textContent = `
    #omniweb-chat-fab{position:fixed;bottom:24px;right:24px;z-index:99999;
      width:60px;height:60px;border-radius:50%;background:#6366f1;color:#fff;
      border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;
      box-shadow:0 4px 14px rgba(0,0,0,.25);transition:transform .2s}
    #omniweb-chat-fab:hover{transform:scale(1.08)}
    #omniweb-chat-fab svg{width:28px;height:28px;fill:currentColor}
    #omniweb-voice-fab{position:fixed;bottom:24px;right:96px;z-index:99999;
      height:44px;border-radius:999px;background:#0f172a;color:#fff;border:1px solid rgba(148,163,184,.3);
      cursor:pointer;display:flex;align-items:center;justify-content:center;padding:0 14px;
      font:600 13px/1 system-ui,sans-serif;box-shadow:0 4px 14px rgba(0,0,0,.22)}
    #omniweb-voice-fab:hover{background:#1e293b}
    #omniweb-voice-panel{position:fixed;bottom:96px;right:24px;z-index:99999;
      width:min(100vw - 1rem,360px);border-radius:16px;padding:14px;
      box-shadow:0 12px 48px rgba(0,0,0,.35);background:#0b1220;color:#e5e7eb;
      display:none;font-family:system-ui,sans-serif}
    #omniweb-voice-panel .omniweb-voice-row{display:flex;align-items:center;gap:10px}
    #omniweb-voice-panel .omniweb-voice-status{flex:1;font-size:13px;color:#cbd5e1}
    #omniweb-voice-panel .omniweb-voice-title{font-weight:700;font-size:14px;color:#fff}
    #omniweb-voice-panel button{border:0;border-radius:999px;padding:8px 12px;cursor:pointer;
      font:600 12px/1 system-ui,sans-serif}
    #omniweb-voice-action{background:#6366f1;color:#fff}
    #omniweb-voice-close{background:#1e293b;color:#fff}
    #omniweb-voice-transcript{margin-top:12px;max-height:180px;overflow:auto;display:flex;
      flex-direction:column;gap:8px}
    .omniweb-voice-line{font-size:13px;line-height:1.35;padding:8px 10px;border-radius:12px}
    .omniweb-voice-line.user{background:#312e81;color:#eef2ff;align-self:flex-end}
    .omniweb-voice-line.assistant{background:#172033;color:#e5e7eb;align-self:flex-start}
    #omniweb-chat-window{position:fixed;bottom:96px;right:24px;z-index:99999;
      width:380px;max-height:520px;border-radius:16px;background:#fff;
      display:flex;flex-direction:column;overflow:hidden;
      box-shadow:0 8px 30px rgba(0,0,0,.18);font-family:system-ui,sans-serif;
      transition:opacity .2s,transform .2s}
    #omniweb-chat-window.hidden{opacity:0;transform:translateY(16px);pointer-events:none}
    #omniweb-chat-header{background:#6366f1;color:#fff;padding:14px 18px;
      font-size:15px;font-weight:600;display:flex;align-items:center;gap:8px}
    #omniweb-chat-header span{flex:1}
    #omniweb-chat-close{background:none;border:none;color:#fff;cursor:pointer;font-size:20px}
    #omniweb-chat-messages{flex:1;overflow-y:auto;padding:14px;display:flex;
      flex-direction:column;gap:10px;min-height:260px;max-height:380px}
    .omniweb-msg{padding:10px 14px;border-radius:14px;max-width:82%;
      font-size:14px;line-height:1.45;word-wrap:break-word}
    .omniweb-msg.assistant{background:#f1f1ff;color:#1e1e2e;align-self:flex-start;
      border-bottom-left-radius:4px}
    .omniweb-msg.shopper{background:#6366f1;color:#fff;align-self:flex-end;
      border-bottom-right-radius:4px}
    .omniweb-msg.system{background:#f9fafb;color:#888;font-size:12px;
      text-align:center;align-self:center}
    #omniweb-chat-input-row{display:flex;border-top:1px solid #eee;padding:8px}
    #omniweb-chat-input{flex:1;border:none;outline:none;padding:10px 12px;
      font-size:14px;background:transparent}
    #omniweb-chat-send{background:#6366f1;color:#fff;border:none;cursor:pointer;
      border-radius:10px;padding:8px 16px;font-size:14px;font-weight:600;
      transition:opacity .15s}
    #omniweb-chat-send:disabled{opacity:.5;cursor:default}
    @media(max-width:480px){#omniweb-chat-window{right:8px;left:8px;
      bottom:80px;width:auto}#omniweb-voice-fab{right:84px;bottom:18px}
      #omniweb-voice-panel{right:8px;left:8px;bottom:80px;width:auto;height:min(100dvh - 96px,680px)}}
  `
  document.head.appendChild(STYLE)

  /* ── DOM ──────────────────────────────────────────────────────── */
  const fab = el("button", { id: "omniweb-chat-fab" })
  fab.innerHTML = `<svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H5.2L4 17.2V4h16v12z"/></svg>`
  fab.onclick = toggleChat
  const voiceFab = el("button", { id: "omniweb-voice-fab", textContent: "Voice" })
  voiceFab.onclick = toggleVoice
  const voicePanel = el("div", { id: "omniweb-voice-panel" })
  voicePanel.innerHTML = `
    <div class="omniweb-voice-row">
      <div>
        <div class="omniweb-voice-title">Voice Assistant</div>
        <div class="omniweb-voice-status" id="omniweb-voice-status">Ready</div>
      </div>
      <button id="omniweb-voice-action" type="button">Start</button>
      <button id="omniweb-voice-close" type="button">Close</button>
    </div>
    <div id="omniweb-voice-transcript"></div>
  `

  const win = el("div", { id: "omniweb-chat-window", className: "hidden" })
  const header = el("div", { id: "omniweb-chat-header" })
  header.innerHTML = `<span>💬 Shopping Assistant</span><button id="omniweb-chat-close">&times;</button>`

  const msgBox = el("div", { id: "omniweb-chat-messages" })
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
  win.append(header, msgBox, inputRow)
  document.body.append(fab, voiceFab, voicePanel, win)

  document.getElementById("omniweb-chat-close").onclick = toggleChat
  document.getElementById("omniweb-voice-close").onclick = closeVoice
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
        fab.style.display = "none"
        voiceFab.style.display = "none"
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
    if (open && !sessionId) startSession()
  }

  function toggleChat() {
    setChatOpen(minimised)
  }

  function toggleVoice() {
    if (voiceOpen) return closeVoice()
    voiceOpen = true
    voicePanel.style.display = "block"
    if (!voiceSession && !voiceBusy) startVoice()
  }

  async function closeVoice() {
    voiceOpen = false
    voicePanel.style.display = "none"
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
          language: (navigator.language || "en").split("-")[0],
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
  function buildContext() {
    return {
      shop_domain: SHOP,
      storefront_session_id: sessionId,
      current_page_url: location.href,
      current_page_title: document.title,
      currency: window.Shopify?.currency?.active || "USD",
      shopper_locale: navigator.language || "en",
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
    trackEvent,
    toggleChat,
    openChat: () => setChatOpen(true),
    closeChat: () => setChatOpen(false),
    isOpen: () => !minimised,
  }
})()

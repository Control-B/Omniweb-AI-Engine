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
    // Western European
    ["en", "🇺🇸 English"],
    ["es", "🇪🇸 Spanish"],
    ["fr", "🇫🇷 French"],
    ["de", "🇩🇪 German"],
    ["it", "🇮🇹 Italian"],
    ["pt", "🇵🇹 Portuguese"],
    ["nl", "🇳🇱 Dutch"],
    ["sv", "🇸🇪 Swedish"],
    ["ro", "🇷🇴 Romanian"],
    // Eastern European
    ["ru", "🇷🇺 Russian"],
    ["uk", "🇺🇦 Ukrainian"],
    ["pl", "🇵🇱 Polish"],
    // Middle East & Turkey
    ["ar", "🇸🇦 Arabic"],
    ["tr", "🇹🇷 Turkish"],
    // South Asia
    ["hi", "🇮🇳 Hindi"],
    ["bn", "🇧🇩 Bengali"],
    // East Asia
    ["zh", "🇨🇳 Chinese"],
    ["ja", "🇯🇵 Japanese"],
    ["ko", "🇰🇷 Korean"],
    // Southeast Asia
    ["id", "🇮🇩 Indonesian"],
    ["vi", "🇻🇳 Vietnamese"],
    ["tl", "🇵🇭 Filipino"],
    // Africa
    ["sw", "🇰🇪 Swahili"],
    // West Africa / Creole
    ["kri", "🇸🇱 Krio"],
    // Sundanese (West Java)
    ["su", "🇮🇩 Sundanese"],
  ]
  let selectedLanguage = detectDefaultLanguage()

  /* ── Styles ───────────────────────────────────────────────────── */
  const STYLE = document.createElement("style")
  STYLE.textContent = `
    @keyframes omniweb-pulse{0%,100%{box-shadow:0 0 0 0 rgba(99,102,241,.5)}50%{box-shadow:0 0 0 10px rgba(99,102,241,0)}}
    @keyframes omniweb-spin{from{transform:rotate(0)}to{transform:rotate(360deg)}}
    @keyframes omniweb-wave{0%,100%{transform:scaleY(.4)}50%{transform:scaleY(1)}}

    /* ── Launcher ── */
    #omniweb-launcher{
      position:fixed;bottom:24px;right:24px;z-index:99999;
      min-width:108px;height:52px;border-radius:999px;
      background:linear-gradient(135deg,#1e1b4b 0%,#3730a3 45%,#6366f1 100%);
      border:1px solid rgba(99,102,241,.6);
      color:#fff;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:9px;
      padding:0 20px;font:700 13px/1 system-ui,sans-serif;letter-spacing:.025em;
      box-shadow:0 4px 24px rgba(99,102,241,.45),0 2px 8px rgba(0,0,0,.35),inset 0 1px 0 rgba(255,255,255,.18);
      transition:transform .18s cubic-bezier(.34,1.56,.64,1),box-shadow .18s}
    #omniweb-launcher:hover{
      transform:translateY(-2px) scale(1.04);
      box-shadow:0 8px 32px rgba(99,102,241,.6),0 4px 12px rgba(0,0,0,.4),inset 0 1px 0 rgba(255,255,255,.22)}
    #omniweb-launcher .omniweb-orb{
      width:20px;height:20px;border-radius:50%;flex-shrink:0;
      background:conic-gradient(from 135deg,#a5b4fc,#818cf8,#6366f1,#4f46e5,#a5b4fc);
      box-shadow:0 0 10px rgba(165,180,252,.7),inset 0 1px 1px rgba(255,255,255,.4)}

    /* ── Chat window ── */
    #omniweb-chat-window{
      position:fixed;bottom:88px;right:24px;z-index:99999;
      width:min(400px,calc(100vw - 20px));max-height:min(680px,calc(100dvh - 106px));
      border-radius:24px;overflow:hidden;display:flex;flex-direction:column;
      background:#0c0e1a;border:1px solid rgba(99,102,241,.25);
      box-shadow:0 24px 80px rgba(0,0,0,.6),0 0 0 1px rgba(99,102,241,.08);
      font-family:system-ui,sans-serif;color:#f1f5f9;
      transition:opacity .22s,transform .22s cubic-bezier(.34,1.56,.64,1)}
    #omniweb-chat-window.hidden{opacity:0;transform:translateY(18px) scale(.97);pointer-events:none}

    /* ── Header ── */
    #omniweb-chat-header{
      padding:14px 16px;display:grid;grid-template-columns:1fr auto auto;align-items:center;gap:10px;
      background:linear-gradient(180deg,#13152a 0%,#0e1020 100%);
      border-bottom:1px solid rgba(99,102,241,.18)}
    #omniweb-chat-header .omniweb-title{
      font-size:14px;font-weight:700;color:#e0e7ff;letter-spacing:.015em;
      display:flex;align-items:center;gap:8px}
    #omniweb-chat-header .omniweb-title-dot{
      width:8px;height:8px;border-radius:50%;background:#4ade80;
      box-shadow:0 0 6px rgba(74,222,128,.7);flex-shrink:0}
    #omniweb-language{
      border:1px solid rgba(99,102,241,.3);border-radius:999px;
      background:rgba(99,102,241,.12);color:#c7d2fe;
      padding:6px 22px 6px 10px;font:600 11px/1 system-ui,sans-serif;
      outline:none;cursor:pointer;-webkit-appearance:none;appearance:none;
      background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%23a5b4fc' stroke-width='1.5' fill='none' stroke-linecap='round'/%3E%3C/svg%3E");
      background-repeat:no-repeat;background-position:right 8px center}
    #omniweb-language option{background:#1a1c2e;color:#e0e7ff}
    #omniweb-chat-close{
      width:30px;height:30px;border-radius:50%;
      background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);
      color:#94a3b8;cursor:pointer;font-size:18px;line-height:1;
      display:flex;align-items:center;justify-content:center;
      transition:background .15s,color .15s}
    #omniweb-chat-close:hover{background:rgba(239,68,68,.15);color:#f87171}

    /* ── Mode row ── */
    #omniweb-mode-row{
      display:grid;grid-template-columns:1fr 1fr;gap:6px;
      padding:10px 12px;background:#0e1020;border-bottom:1px solid rgba(99,102,241,.12)}
    .omniweb-mode{
      border:1px solid rgba(99,102,241,.2);border-radius:999px;padding:8px 12px;cursor:pointer;
      background:transparent;color:#64748b;font:600 12px/1 system-ui,sans-serif;
      transition:all .15s}
    .omniweb-mode.active{
      background:linear-gradient(135deg,#4338ca,#6366f1);color:#fff;border-color:transparent;
      box-shadow:0 4px 16px rgba(99,102,241,.35)}
    .omniweb-mode:not(.active):hover{color:#a5b4fc;border-color:rgba(99,102,241,.4)}

    /* ── Messages ── */
    #omniweb-chat-messages{
      flex:1;overflow-y:auto;padding:16px 14px;display:flex;
      flex-direction:column;gap:10px;min-height:200px;max-height:300px;
      background:#0c0e1a;scrollbar-width:thin;scrollbar-color:rgba(99,102,241,.25) transparent}
    #omniweb-chat-messages::-webkit-scrollbar{width:4px}
    #omniweb-chat-messages::-webkit-scrollbar-thumb{background:rgba(99,102,241,.3);border-radius:4px}
    .omniweb-msg{
      padding:10px 14px;border-radius:16px;max-width:84%;
      font-size:14px;line-height:1.5;word-wrap:break-word}
    .omniweb-msg.assistant{
      background:rgba(99,102,241,.14);color:#e0e7ff;align-self:flex-start;
      border-bottom-left-radius:4px;border:1px solid rgba(99,102,241,.2)}
    .omniweb-msg.shopper{
      background:linear-gradient(135deg,#4338ca,#6366f1);color:#fff;align-self:flex-end;
      border-bottom-right-radius:4px}
    .omniweb-msg.system{
      background:rgba(100,116,139,.12);color:#64748b;font-size:12px;
      text-align:center;align-self:center;border-radius:8px;padding:6px 12px}

    /* ── Voice panel ── */
    #omniweb-voice-panel{display:none;flex-direction:column;gap:0;background:#0e1020}
    #omniweb-voice-panel.active{display:flex}
    #omniweb-voice-orb-area{
      display:flex;flex-direction:column;align-items:center;justify-content:center;
      padding:24px 16px 16px;gap:14px;background:#0c0e1a}
    #omniweb-voice-orb{
      width:72px;height:72px;border-radius:50%;position:relative;cursor:default;
      background:conic-gradient(from 180deg,#22d3ee,#818cf8,#a855f7,#ec4899,#22d3ee);
      box-shadow:0 0 32px rgba(129,140,248,.35)}
    #omniweb-voice-orb::before{
      content:'';position:absolute;inset:4px;border-radius:50%;
      background:radial-gradient(circle at 38% 32%,#1e1b4b,#0c0e1a 70%)}
    #omniweb-voice-orb.active{animation:omniweb-pulse 1.8s ease-in-out infinite}
    #omniweb-voice-bars{display:flex;align-items:center;gap:3px;height:20px}
    #omniweb-voice-bars span{
      display:inline-block;width:3px;background:#6366f1;border-radius:999px;
      height:100%;transform:scaleY(.4);transition:transform .2s}
    #omniweb-voice-bars.active span:nth-child(1){animation:omniweb-wave 1s .0s ease-in-out infinite}
    #omniweb-voice-bars.active span:nth-child(2){animation:omniweb-wave 1s .1s ease-in-out infinite}
    #omniweb-voice-bars.active span:nth-child(3){animation:omniweb-wave 1s .2s ease-in-out infinite}
    #omniweb-voice-bars.active span:nth-child(4){animation:omniweb-wave 1s .15s ease-in-out infinite}
    #omniweb-voice-bars.active span:nth-child(5){animation:omniweb-wave 1s .05s ease-in-out infinite}
    #omniweb-voice-status-text{font-size:12px;color:#64748b;text-align:center}
    #omniweb-voice-action{
      border:0;border-radius:999px;padding:11px 28px;cursor:pointer;
      font:700 13px/1 system-ui,sans-serif;letter-spacing:.02em;
      background:linear-gradient(135deg,#4338ca,#6366f1);color:#fff;
      box-shadow:0 4px 16px rgba(99,102,241,.4);
      transition:transform .15s,box-shadow .15s}
    #omniweb-voice-action:hover{transform:scale(1.04);box-shadow:0 6px 20px rgba(99,102,241,.55)}
    #omniweb-voice-action.ending{background:linear-gradient(135deg,#be123c,#f43f5e)}
    #omniweb-voice-controls{
      display:flex;align-items:center;gap:10px;padding:12px 16px;
      border-top:1px solid rgba(99,102,241,.1)}
    #omniweb-voice-controls .omniweb-voice-label{
      flex:1;font-size:12px;color:#475569;font-weight:600;letter-spacing:.04em;text-transform:uppercase}
    #omniweb-voice-transcript{
      padding:10px 14px;max-height:130px;overflow:auto;display:flex;
      flex-direction:column;gap:6px;background:#0c0e1a;
      border-top:1px solid rgba(99,102,241,.1);
      scrollbar-width:thin;scrollbar-color:rgba(99,102,241,.2) transparent}
    .omniweb-voice-line{font-size:13px;line-height:1.4;padding:7px 11px;border-radius:12px}
    .omniweb-voice-line.user{
      background:rgba(99,102,241,.18);color:#c7d2fe;align-self:flex-end;
      border-bottom-right-radius:3px;max-width:85%}
    .omniweb-voice-line.assistant{
      background:rgba(30,27,75,.5);color:#94a3b8;align-self:flex-start;
      border-bottom-left-radius:3px;max-width:85%}

    /* ── Input row ── */
    #omniweb-chat-input-row{
      display:flex;align-items:center;gap:8px;
      border-top:1px solid rgba(99,102,241,.12);padding:12px 14px;background:#0e1020}
    #omniweb-chat-input{
      flex:1;border:1px solid rgba(99,102,241,.2);outline:none;
      padding:10px 14px;font-size:14px;color:#e0e7ff;
      background:rgba(99,102,241,.08);border-radius:12px;
      transition:border-color .15s}
    #omniweb-chat-input::placeholder{color:#475569}
    #omniweb-chat-input:focus{border-color:rgba(99,102,241,.5)}
    #omniweb-chat-send{
      width:38px;height:38px;border-radius:50%;flex-shrink:0;
      background:linear-gradient(135deg,#4338ca,#6366f1);color:#fff;
      border:none;cursor:pointer;font-size:16px;
      display:flex;align-items:center;justify-content:center;
      box-shadow:0 2px 10px rgba(99,102,241,.4);
      transition:transform .15s,box-shadow .15s}
    #omniweb-chat-send:hover:not(:disabled){transform:scale(1.08);box-shadow:0 4px 14px rgba(99,102,241,.55)}
    #omniweb-chat-send:disabled{opacity:.4;cursor:default}

    @media(max-width:480px){
      #omniweb-chat-window{right:8px;left:8px;bottom:80px;width:auto}
      #omniweb-launcher{right:14px;bottom:16px}
      #omniweb-chat-header{grid-template-columns:1fr auto auto}}
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
    <span class="omniweb-title"><span class="omniweb-title-dot"></span>Omniweb AI</span>
    <select id="omniweb-language" aria-label="Assistant language">${languageOptions}</select>
    <button id="omniweb-chat-close" type="button" aria-label="Close">&#x2715;</button>
  `
  const modeRow = el("div", { id: "omniweb-mode-row" })
  modeRow.innerHTML = `
    <button class="omniweb-mode active" id="omniweb-chat-mode" type="button">Text</button>
    <button class="omniweb-mode" id="omniweb-voice-mode" type="button">Voice</button>
  `

  const msgBox = el("div", { id: "omniweb-chat-messages" })
  const voicePanel = el("div", { id: "omniweb-voice-panel" })
  voicePanel.innerHTML = `
    <div id="omniweb-voice-orb-area">
      <div id="omniweb-voice-orb"></div>
      <div id="omniweb-voice-bars">
        <span></span><span></span><span></span><span></span><span></span>
      </div>
      <div id="omniweb-voice-status-text" id="omniweb-voice-status">Choose a language, then start.</div>
      <button id="omniweb-voice-action" type="button">Start Voice</button>
    </div>
    <div id="omniweb-voice-transcript"></div>
  `
  const inputRow = el("div", { id: "omniweb-chat-input-row" })
  const input = el("input", {
    id: "omniweb-chat-input",
    placeholder: "Ask me anything...",
  })
  const sendBtn = el("button", { id: "omniweb-chat-send" })
  sendBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></svg>`
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
    const node = document.getElementById("omniweb-voice-status-text")
    if (node) node.textContent = text
  }

  function setVoiceAction(text) {
    const node = document.getElementById("omniweb-voice-action")
    if (!node) return
    const active = text === "End"
    node.textContent = active ? "End Session" : "Start Voice"
    node.classList.toggle("ending", active)
    const orb = document.getElementById("omniweb-voice-orb")
    const bars = document.getElementById("omniweb-voice-bars")
    if (orb) orb.classList.toggle("active", active)
    if (bars) bars.classList.toggle("active", active)
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

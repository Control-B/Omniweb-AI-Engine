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
  let sessionId = null
  let endpoints = {}
  let greeting = ""
  let minimised = true
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
      bottom:80px;width:auto}}
  `
  document.head.appendChild(STYLE)

  /* ── DOM ──────────────────────────────────────────────────────── */
  const fab = el("button", { id: "omniweb-chat-fab" })
  fab.innerHTML = `<svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H5.2L4 17.2V4h16v12z"/></svg>`
  fab.onclick = toggleChat

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
  document.body.append(fab, win)

  document.getElementById("omniweb-chat-close").onclick = toggleChat
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
      endpoints = data.endpoints || {}
      greeting = data.greeting || "Hi! How can I help you today?"
      if (!data.assistant_enabled) {
        fab.style.display = "none"
        return
      }
    } catch (err) {
      console.error("[Omniweb] bootstrap error", err)
    }
  }

  /* ── Chat ─────────────────────────────────────────────────────── */
  function toggleChat() {
    minimised = !minimised
    win.classList.toggle("hidden", minimised)
    if (!minimised && !sessionId) startSession()
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
  window.OmniwebChat = { trackEvent, toggleChat }
})()
